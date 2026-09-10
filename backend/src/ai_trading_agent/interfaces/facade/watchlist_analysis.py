"""Composition for focused, cached watchlist research summaries."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

from fastapi import FastAPI

from ai_trading_agent.application.watchlist_analysis import (
    GetLatestWatchlistAnalysisHandler,
    ListLatestWatchlistAnalysesHandler,
    SaveWatchlistAnalysisHandler,
)
from ai_trading_agent.domain.aggregate.watchlist import WatchlistItem
from ai_trading_agent.domain.aggregate.watchlist_analysis import (
    AnalysisTag,
    WatchlistAnalysisSnapshot,
)
from ai_trading_agent.domain.enums.research import WatchlistAnalysisStatus
from ai_trading_agent.infrastructure.config.news import OpenAICompatibleLLMSettings
from ai_trading_agent.infrastructure.config.providers import WatchlistAnalysisSettings
from ai_trading_agent.infrastructure.rpc.llm_advisor import OpenAICompatibleResearchAdvisor
from ai_trading_agent.interfaces.facade.disciplines import evaluate_active_disciplines
from ai_trading_agent.interfaces.facade.portfolio import (
    watchlist_analysis_repository,
    watchlist_repository,
)
from ai_trading_agent.interfaces.facade.research_workspace import (
    latest_quote,
    research,
    technical_study,
)
from ai_trading_agent.interfaces.model.http import (
    DisciplineDecisionResponse,
    QuoteQuery,
    ResearchRequest,
    TechnicalRequest,
)


async def latest_watchlist_analyses(app: FastAPI) -> list[WatchlistAnalysisSnapshot]:
    return await ListLatestWatchlistAnalysesHandler(
        watchlist_analysis_repository(app)
    ).handle()


async def latest_watchlist_analysis(
    app: FastAPI, item_id: str
) -> WatchlistAnalysisSnapshot | None:
    return await GetLatestWatchlistAnalysisHandler(watchlist_analysis_repository(app)).handle(
        item_id
    )


async def refresh_watchlist_analysis(
    app: FastAPI,
    item: WatchlistItem,
    *,
    force: bool = False,
) -> WatchlistAnalysisSnapshot:
    """Collect one selected instrument sequentially and persist a bounded result."""
    settings = WatchlistAnalysisSettings.from_environment()
    repository = watchlist_analysis_repository(app)
    existing = await GetLatestWatchlistAnalysisHandler(repository).handle(str(item.item_id))
    now = datetime.now(UTC)
    if (
        not force
        and existing is not None
        and now - existing.observed_at < timedelta(seconds=settings.interval_seconds)
    ):
        return existing

    query = QuoteQuery(
        symbol=item.instrument.symbol,
        market=item.instrument.market,
        instrument_type=item.instrument.instrument_type,
    )
    notices: list[str] = []
    tags: list[AnalysisTag] = []
    context: list[str] = []
    quote = None
    try:
        quote = await latest_quote(item.instrument)
        tags.extend(_quote_tags(quote.last_price, quote.previous_close))
        context.append(
            f"Quote: {quote.last_price} {quote.instrument.currency}; "
            f"observed_at={quote.observed_at.isoformat()}; source={quote.source}."
        )
    except Exception as error:
        notices.append(f"行情暂不可用：{error}")

    report = await research(
        ResearchRequest(
            symbol=query.symbol,
            market=query.market,
            instrument_type=query.instrument_type,
        )
    )
    notices.extend(report.notices)
    tags.extend(_research_tags(report.fundamentals, report.capital_flow, report.news_sentiment))
    context.append(f"Research: {report.model_dump_json(exclude_none=True)}")

    try:
        study = await technical_study(
            TechnicalRequest(
                symbol=query.symbol,
                market=query.market,
                instrument_type=query.instrument_type,
            )
        )
        tags.extend(
            _technical_tags(
                study.assessment["trend"],
                study.assessment["momentum"],
                study.assessment["volume_pressure"],
            )
        )
        context.append(
            "Technical assessment: "
            + str(study.assessment)
            + "; indicators="
            + str(study.indicators)
        )
    except Exception as error:
        notices.append(f"技术研究暂不可用：{error}")

    if quote is not None:
        try:
            decisions = await evaluate_active_disciplines(app, item.instrument, quote)
            decision_responses = [
                DisciplineDecisionResponse.from_domain(decision) for decision in decisions
            ]
            tags.extend(
                AnalysisTag("discipline", f"纪律：{item.label}", _decision_tone(item.status))
                for item in decision_responses
            )
            if decision_responses:
                context.append(
                    "Deterministic personal-discipline status (explain only, do not change): "
                    + "; ".join(
                        f"{item.label}: {item.rationale}" for item in decision_responses
                    )
                )
        except Exception as error:
            notices.append(f"个人纪律暂不可用：{error}")

    ai_summary = await _summarize_with_ai(context, notices)
    if ai_summary is not None:
        tags.append(AnalysisTag("ai", "AI 解读已更新", "info"))
    elif context:
        notices.append("AI 解读暂不可用；已保留可解释的数据标签。")

    status = _analysis_status(quote is not None, notices)
    snapshot = WatchlistAnalysisSnapshot(
        analysis_id=uuid4(),
        watchlist_item_id=item.item_id,
        instrument=item.instrument,
        observed_at=now,
        status=status,
        tags=tuple(_unique_tags(tags)),
        ai_summary=ai_summary,
        notices=tuple(notices[:32]),
    )
    return await SaveWatchlistAnalysisHandler(repository).handle(snapshot)


async def refresh_all_watchlist_analyses(app: FastAPI) -> list[WatchlistAnalysisSnapshot]:
    """Refresh a bounded personal list in sequence; never scan the market universe."""
    settings = WatchlistAnalysisSettings.from_environment()
    items = await watchlist_repository(app).list()
    return [
        await refresh_watchlist_analysis(app, item)
        for item in items[: settings.max_items_per_run]
    ]


def _quote_tags(last_price: object, previous_close: object) -> list[AnalysisTag]:
    if previous_close is None or previous_close == 0:
        return [AnalysisTag("quote", f"现价：{last_price}", "info")]
    change = (last_price - previous_close) / previous_close * 100
    tone = "positive" if change > 0 else "negative" if change < 0 else "neutral"
    direction = "上涨" if change > 0 else "下跌" if change < 0 else "平盘"
    return [AnalysisTag("quote", f"日内：{direction} {change:.2f}%", tone)]


def _research_tags(
    fundamentals: dict[str, object] | None,
    capital_flow: dict[str, object] | None,
    news_sentiment: dict[str, object] | None,
) -> list[AnalysisTag]:
    tags: list[AnalysisTag] = []
    if news_sentiment is not None and news_sentiment.get("label") is not None:
        label = str(news_sentiment["label"])
        mapping = {"positive": ("积极", "positive"), "negative": ("消极", "negative")}
        display, tone = mapping.get(label, ("中性", "neutral"))
        tags.append(AnalysisTag("sentiment", f"情绪：{display}", tone))
    if fundamentals is not None and fundamentals.get("score") is not None:
        tags.append(AnalysisTag("fundamentals", f"基本面：{fundamentals['score']} 分", "info"))
    if capital_flow is not None and capital_flow.get("direction") is not None:
        direction = str(capital_flow["direction"])
        mapping = {"inflow": ("资金：流入", "positive"), "outflow": ("资金：流出", "negative")}
        display, tone = mapping.get(direction, ("资金：中性", "neutral"))
        tags.append(AnalysisTag("capital_flow", display, tone))
    return tags


def _technical_tags(trend: object, momentum: object, volume_pressure: object) -> list[AnalysisTag]:
    return [
        AnalysisTag("trend", f"趋势：{trend}", _technical_tone(str(trend))),
        AnalysisTag("momentum", f"动量：{momentum}", _technical_tone(str(momentum))),
        AnalysisTag("volume", f"量能：{volume_pressure}", _technical_tone(str(volume_pressure))),
    ]


def _technical_tone(value: str) -> str:
    if any(item in value for item in ("偏多", "上升", "强")):
        return "positive"
    if any(item in value for item in ("偏空", "下降", "弱")):
        return "negative"
    return "neutral"


def _decision_tone(status: object) -> str:
    return {
        "buy_candidate": "positive",
        "add_condition_met": "info",
        "take_profit": "positive",
        "exit": "negative",
    }.get(str(status), "neutral")


def _analysis_status(has_quote: bool, notices: list[str]) -> WatchlistAnalysisStatus:
    if not has_quote:
        return WatchlistAnalysisStatus.FAILED
    if notices:
        return WatchlistAnalysisStatus.PARTIAL
    return WatchlistAnalysisStatus.COMPLETED


def _unique_tags(tags: list[AnalysisTag]) -> list[AnalysisTag]:
    unique: dict[str, AnalysisTag] = {}
    for tag in tags:
        unique[tag.category] = tag
    return list(unique.values())[:16]


async def _summarize_with_ai(context: list[str], notices: list[str]) -> str | None:
    if not context:
        return None
    try:
        adviser = OpenAICompatibleResearchAdvisor(OpenAICompatibleLLMSettings.from_environment())
        answer = await adviser.answer(
            question=(
                "请将该自选标的的已确认数据浓缩为 3 条以内、总计不超过 300 字的"
                "中文研究摘要。只解释事实、缺口和规则状态，不给出个性化交易指令。"
            ),
            context="\n\n".join(context),
        )
        return answer[:2_000]
    except Exception as error:
        notices.append(f"AI 解读暂不可用：{error}")
        return None
