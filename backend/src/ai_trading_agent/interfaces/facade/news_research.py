"""Compose verified identity metadata and public news without additional LLM calls."""

import asyncio
from datetime import UTC, datetime, timedelta

from ai_trading_agent.domain.aggregate.market import Instrument
from ai_trading_agent.domain.enums.market import InstrumentType, Market
from ai_trading_agent.domain.service.news_relevance import NewsSubject, analyze_relevant_news
from ai_trading_agent.infrastructure.config.providers import TushareSettings
from ai_trading_agent.infrastructure.rpc.tushare_news_subject import TushareNewsSubjectProvider
from ai_trading_agent.interfaces.adapter.environment import load_runtime_environment
from ai_trading_agent.interfaces.facade.instruments import resolve_instrument_identity

_subjects: dict[Instrument, tuple[datetime, NewsSubject]] = {}
_subject_lock = asyncio.Lock()


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
    articles = await _news_collector.handle(sources=sources, lookback=timedelta(hours=24))
    result = analyze_relevant_news(subject, articles, now=datetime.now(UTC))
    result["limitations"] = [
        "基于已采集样本及关键词规则，不代表全网完整覆盖；同句涉及多家公司时仍可能存在归因歧义。"
    ]
    if not subject.industries:
        result["limitations"].append("行业分类暂缺，未猜测所属行业。")
    if not subject.names:
        result["limitations"].append("名称暂缺，仅按明确证券代码匹配。")
    return result
