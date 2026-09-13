"""Dashboard market-question orchestration with bounded, source-labelled context."""

from __future__ import annotations

import asyncio
import re
from collections.abc import Awaitable
from datetime import UTC, datetime

from ai_trading_agent.application.market_assistant import AnswerMarketQuestionHandler
from ai_trading_agent.domain.aggregate.instrument_identity import CatalogInstrument
from ai_trading_agent.domain.aggregate.market_assistant import MarketAssistantAnswer
from ai_trading_agent.domain.aggregate.market_brief import PostMarketBrief
from ai_trading_agent.infrastructure.config.news import OpenAICompatibleLLMSettings
from ai_trading_agent.infrastructure.rpc.llm_advisor import OpenAICompatibleResearchAdvisor
from ai_trading_agent.interfaces.facade.instruments import search_instrument_catalog
from ai_trading_agent.interfaces.facade.market_brief import post_market_brief
from ai_trading_agent.interfaces.facade.research_workspace import latest_news
from ai_trading_agent.interfaces.model.http import DEFAULT_NEWS_SOURCES, NewsItemResponse

_COLLECTION_TIMEOUT_SECONDS = 15
_MODEL_TIMEOUT_SECONDS = 35
_FUND_KEYWORDS = ("etf", "基金", "lof", "reits")
_CATALOGUE_KEYWORDS = _FUND_KEYWORDS + ("股票", "个股", "标的", "科技", "白糖")
_TOPIC_WORDS = (
    "我想投资",
    "我想了解",
    "帮我看看",
    "都有哪些",
    "有哪些",
    "什么是",
    "是什么",
    "相关的",
    "相关",
    "设计",
    "股票",
    "个股",
    "基金",
    "标的",
    "ETF",
    "etf",
    "LOF",
    "lof",
    "REITs",
    "reits",
    "可以",
    "吗",
    "呢",
)


async def answer_market_question(question: str) -> MarketAssistantAnswer:
    """Answer a dashboard question without scanning a market-wide universe.

    The focused sources run concurrently and each has a bounded timeout.  A
    source outage therefore yields a clearly labelled partial answer rather
    than a failed dashboard or an invented market conclusion.
    """
    normalized_question = question.strip()
    if not normalized_question:
        raise ValueError("market question must not be empty")

    notices: list[str] = []
    sources: list[str] = []
    catalogue_spec = _catalogue_spec(normalized_question)
    brief_task = _collect(post_market_brief(), "指数与板块快照暂不可用", notices)
    news_task = _collect(
        latest_news(list(DEFAULT_NEWS_SOURCES)), "公开财经资讯暂不可用", notices
    )
    catalogue_task = (
        _collect(
            search_instrument_catalog(
                catalogue_spec[0], asset_types=catalogue_spec[1], limit=6
            ),
            "相关标的目录暂不可用",
            notices,
        )
        if catalogue_spec is not None
        else _empty_candidates()
    )
    brief, news, candidates = await asyncio.gather(brief_task, news_task, catalogue_task)

    context: list[str] = []
    if brief is not None:
        sources.append("同花顺指数与行业板块快照")
        context.append(_brief_context(brief))
    if news:
        sources.append("公开财经资讯（东方财富优先，新浪降级）")
        context.append(_news_context(news))
    if catalogue_spec is not None:
        sources.append("同花顺标的目录")
    if candidates:
        context.append(_catalogue_context(candidates))
    elif catalogue_spec is not None:
        notices.append("公开标的目录未检索到与问题直接匹配的候选。")

    fallback = _fallback_answer(normalized_question, brief, news, candidates, catalogue_spec)
    answer = fallback
    if context:
        try:
            model_answer = _clean_answer(
                await _model_answer(normalized_question, "\n\n".join(context))
            )
            if model_answer:
                answer = model_answer
            else:
                notices.append("AI 模型未返回可读答复，以下内容已按可用数据整理。")
        except Exception:
            notices.append("AI 模型暂不可用，以下内容已按可用数据整理。")

    return MarketAssistantAnswer(
        answer=answer,
        generated_at=datetime.now(UTC),
        sources=tuple(sources),
        notices=tuple(notices),
        candidates=tuple(candidates or ()),
    )


async def _collect[T](
    awaitable: Awaitable[T],
    unavailable_notice: str,
    notices: list[str],
) -> T | None:
    try:
        return await asyncio.wait_for(awaitable, timeout=_COLLECTION_TIMEOUT_SECONDS)
    except Exception:
        notices.append(unavailable_notice)
        return None


async def _empty_candidates() -> list[CatalogInstrument]:
    return []


async def _model_answer(question: str, context: str) -> str:
    advisor = OpenAICompatibleResearchAdvisor(OpenAICompatibleLLMSettings.from_environment())
    answer = await asyncio.wait_for(
        AnswerMarketQuestionHandler(advisor).handle(
            question=(
                f"{question}\n\n请用以下纯文本版式回答：结论：；市场与数据：；"
                "相关候选：；下一步：；风险提示：。每项 1 至 2 句，简明中文。"
                "不得使用 Markdown 标记（#、*、_、反引号或表格）。候选只能复述"
                "已给出的标的目录，不得编造代码或把候选表述为交易指令。"
            ),
            context=context,
        ),
        timeout=_MODEL_TIMEOUT_SECONDS,
    )
    cleaned = _clean_answer(answer)
    if not cleaned:
        raise ValueError("model returned no readable market answer")
    return cleaned


def _catalogue_spec(question: str) -> tuple[str, tuple[str, ...]] | None:
    lower = question.lower()
    if not any(keyword.lower() in lower for keyword in _CATALOGUE_KEYWORDS):
        return None
    topic = _catalogue_topic(question)
    if len(topic) < 2:
        return None
    asset_types = (
        ("fund-etf", "fund-lof")
        if any(keyword.lower() in lower for keyword in _FUND_KEYWORDS)
        else ("a-share",)
    )
    return topic, asset_types


def _catalogue_topic(question: str) -> str:
    topic = question
    for word in _TOPIC_WORDS:
        topic = topic.replace(word, " ")
    topic = re.sub(r"[^\w\u4e00-\u9fff]+", " ", topic)
    parts = [part for part in topic.split() if len(part) >= 2]
    return parts[0] if parts else ""


def _brief_context(brief: PostMarketBrief) -> str:
    indices = "；".join(
        f"{item.name} {item.last_price} {_change_label(item.change_percent)}"
        for item in brief.indices
    )
    leaders = "、".join(
        f"{item.name} {_change_label(item.change_percent)}" for item in brief.leading_sectors
    )
    laggards = "、".join(
        f"{item.name} {_change_label(item.change_percent)}" for item in brief.lagging_sectors
    )
    return (
        "Source: 同花顺指数与行业板块快照。\n"
        f"Observed at: {brief.observed_at.isoformat()}\n"
        f"Indices: {indices}\nLeading sectors: {leaders}\nLagging sectors: {laggards}"
    )


def _news_context(news: list[NewsItemResponse]) -> str:
    items = "\n".join(
        f"- {item.publisher} | {item.published_at} | {item.title} | "
        f"sentiment={item.sentiment}; excerpt={_compact(item.content, 180)}"
        for item in news[:5]
    )
    return f"Source: 公开财经资讯。\n{items}"


def _catalogue_context(candidates: list[CatalogInstrument]) -> str:
    items = "\n".join(
        f"- {item.symbol} | {item.name} | asset_type={item.asset_type} | "
        f"exchange={item.exchange or 'not supplied'}"
        for item in candidates
    )
    return f"Source: 同花顺标的目录。\n{items}"


def _fallback_answer(
    question: str,
    brief: PostMarketBrief | None,
    news: list[NewsItemResponse] | None,
    candidates: list[CatalogInstrument] | None,
    catalogue_spec: tuple[str, tuple[str, ...]] | None,
) -> str:
    lines = [f"结论：已围绕“{_compact(question, 80)}”汇总当前可用研究数据。"]
    if brief is not None:
        index_summary = "；".join(
            f"{item.name}{_change_label(item.change_percent)}" for item in brief.indices
        )
        leading = "、".join(item.name for item in brief.leading_sectors)
        lagging = "、".join(item.name for item in brief.lagging_sectors)
        lines.append(
            f"市场与数据：{index_summary}。行业涨幅居前为{leading}；靠后为{lagging}。"
        )
    else:
        lines.append("市场与数据：当前未取得指数快照，不能据此判断大盘强弱。")
    if candidates:
        matches = "、".join(f"{item.name}（{item.symbol}）" for item in candidates)
        lines.append(f"相关候选：目录检索到{matches}。它们是主题匹配候选，并非推荐名单。")
    elif catalogue_spec is not None:
        lines.append("相关候选：公开目录未返回直接匹配项，可换用更具体的主题、基金名称或代码查询。")
    else:
        lines.append("相关候选：本问题未触发主题标的检索，可继续询问某一主题、股票或 ETF。")
    if news:
        headlines = "；".join(_compact(item.title, 58) for item in news[:3])
        lines.append(f"资讯脉络：近期可用标题包括{headlines}。请结合原文与发布时间复核影响。")
    else:
        lines.append("资讯脉络：当前未取得可用公开资讯，未据此推断情绪或事件影响。")
    lines.append("下一步：可指定一个代码或名称，再在自选跟踪中查看行情、K 线、财务与个人纪律。")
    lines.append("风险提示：市场快照和公开资讯具有时效性；候选与解读仅供研究，不构成交易指令。")
    return "\n".join(lines)


def _change_label(value: object) -> str:
    if value is None:
        return "涨跌幅未提供"
    number = float(value)
    return f"{number:+.2f}%"


def _compact(value: str, limit: int) -> str:
    normalized = " ".join(value.split())
    return normalized if len(normalized) <= limit else f"{normalized[:limit - 1]}…"


def _clean_answer(value: str) -> str:
    lines = []
    for line in value.splitlines():
        cleaned = re.sub(r"[*_`#]+", "", line).strip()
        cleaned = re.sub(r"^(?:[-•]|\d+[.)])\s*", "", cleaned)
        if cleaned:
            lines.append(cleaned)
    return "\n".join(lines)[:3_000]
