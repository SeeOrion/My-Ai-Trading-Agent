"""Compose public website feeds, verified attribution and bounded LLM interpretation."""

import asyncio
import os
from contextvars import ContextVar
from dataclasses import replace
from decimal import Decimal
from datetime import UTC, datetime, timedelta

from ai_trading_agent.domain.aggregate.market import Instrument
from ai_trading_agent.domain.enums.market import InstrumentType, Market
from ai_trading_agent.domain.service.news_relevance import NewsSubject, analyze_relevant_news
from ai_trading_agent.infrastructure.config.providers import TushareSettings
from ai_trading_agent.infrastructure.rpc.tushare_news_subject import TushareNewsSubjectProvider
from ai_trading_agent.interfaces.adapter.environment import load_runtime_environment
from ai_trading_agent.interfaces.facade.instruments import resolve_instrument_identity
from ai_trading_agent.application.news_brief import CachedNewsBriefs
from ai_trading_agent.infrastructure.rpc.public_news_search import PublicNewsSearch
from ai_trading_agent.infrastructure.rpc.llm_news import OpenAICompatibleNewsAnalyzer
from ai_trading_agent.infrastructure.config.news import OpenAICompatibleLLMSettings
from ai_trading_agent.infrastructure.rpc.llm_usage import usage_feature, record_usage

_subjects: dict[Instrument, tuple[datetime, NewsSubject]] = {}
_subject_lock = asyncio.Lock()
_search = PublicNewsSearch()
_briefs = CachedNewsBriefs()
skip_news_model = ContextVar("skip_news_model", default=False)


async def news_subject(instrument: Instrument) -> NewsSubject:
    async with _subject_lock:
        now = datetime.now(UTC)
        cached = _subjects.get(instrument)
        if cached and cached[0] > now:
            return cached[1]
        load_runtime_environment()
        subject = None
        identity = None
        resolved = instrument
        if "." not in instrument.symbol:
            try:
                identity = await asyncio.wait_for(
                    resolve_instrument_identity(instrument), timeout=6
                )
                if identity:
                    resolved = identity.instrument
            except Exception:
                pass
        if (
            instrument.market is Market.A_SHARE
            and instrument.instrument_type is InstrumentType.EQUITY
        ):
            try:
                subject = await TushareNewsSubjectProvider(
                    TushareSettings.from_environment()
                ).resolve(resolved)
            except Exception:
                pass
        if subject is None:
            try:
                identity = identity or await asyncio.wait_for(
                    resolve_instrument_identity(instrument), timeout=6
                )
                if identity:
                    subject = NewsSubject(
                        instrument.symbol, (identity.display_name,), source=identity.source
                    )
            except Exception:
                pass
        subject = subject or NewsSubject(instrument.symbol)
        if len(_subjects) >= 512:
            _subjects.pop(next(iter(_subjects)))
        _subjects[instrument] = (
            now + timedelta(hours=12) if subject.industries else now + timedelta(minutes=10),
            subject,
        )
        return subject


async def instrument_news_research(instrument: Instrument, sources: list[str]) -> dict:
    # Local import avoids the research workspace's facade composition cycle.
    from ai_trading_agent.interfaces.facade.research_workspace import _news_collector

    subject = await news_subject(instrument)
    # Search only verified names/industry and unambiguous local numeric codes.
    code = subject.symbol.split(".")[0]
    terms = (*subject.names[:1], *((code,) if code.isdigit() else ()), *subject.industries[:1])
    fetched = await asyncio.gather(
        _news_collector.handle(sources=sources, lookback=timedelta(hours=24)),
        _search.search(terms), return_exceptions=True,
    )
    articles = [article for batch in fetched if isinstance(batch, list) for article in batch]
    result = analyze_relevant_news(subject, articles, now=datetime.now(UTC))
    result["limitations"] = [
        "基于已采集样本及关键词规则，不代表全网完整覆盖；同句涉及多家公司时仍可能存在归因歧义。"
    ]
    if not subject.industries:
        result["limitations"].append("行业分类暂缺，未猜测所属行业。")
    if not subject.names:
        result["limitations"].append("名称暂缺，仅按明确证券代码匹配。")
    if any(isinstance(batch, BaseException) for batch in fetched):
        result["limitations"].append("部分公开资讯源暂不可用，已保留其他来源结果。")
    await _interpret_news(result, subject)
    return result


async def _interpret_news(result, subject):
    if skip_news_model.get():
        result["llm_analysis"] = {"status": "handled_by_research_agent"}
        return
    if os.environ.get("NEWS_LLM_ENABLED", "true").lower() != "true":
        result["llm_analysis"] = {"status": "disabled"}
        return
    token = usage_feature.set("news_analysis")
    try:
        settings = replace(OpenAICompatibleLLMSettings.from_environment(), timeout_seconds=20)
        limit = max(0, min(60, int(os.environ.get("NEWS_LLM_MAX_CALLS_PER_HOUR", "12"))))
        brief = await _briefs.interpret(
            analyzer=OpenAICompatibleNewsAnalyzer(settings), model=settings.model,
            subject=" / ".join((subject.symbol, *subject.names)), layer="个股情绪（不代表大盘情绪）",
            evidence=result["instrument"]["evidence"], hourly_limit=limit,
        )
        result["llm_analysis"] = brief
        if brief.get("cached") and brief.get("status") == "completed":
            await record_usage(model=settings.model, status="reused", reason="news_content_unchanged")
        if brief.get("status") == "completed":
            result["summary"] += " AI 新闻研判：" + brief["summary"]
            # Only sufficiently supported direct news may enter the news factor.
            # Industry/macro layers remain contextual; discipline/risk gates are unchanged.
            if result["factor_eligible"] and brief["confidence"] >= 0.65:
                score = {"positive": Decimal("0.5"), "neutral": Decimal(0), "negative": Decimal("-0.5")}[brief["sentiment"]]
                result["lexicon_score"] = result["score"]
                result["score"] = score
                result["label"] = brief["sentiment"]
                result["source"] = "public_news_llm_attributed_v1"
        elif brief.get("status") not in {"no_evidence"}:
            result["limitations"].append("新闻 AI 研判暂不可用或达到调用限额；当前使用关键词情绪，不影响行情与纪律复核。")
    except Exception:
        result["llm_analysis"] = {"status": "unavailable"}
        result["limitations"].append("新闻 AI 未完成，保留关键词分析。")
    finally:
        usage_feature.reset(token)
