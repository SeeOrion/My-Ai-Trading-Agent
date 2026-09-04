"""Interface-level orchestration for market, news, research and strategy workspaces."""

from __future__ import annotations

from datetime import timedelta
from uuid import UUID

from fastapi import FastAPI

from ai_trading_agent.application.a_share_quote_failover import (
    AShareQuoteFailover,
    get_single_quote,
)
from ai_trading_agent.application.news import CollectLatestNewsHandler
from ai_trading_agent.application.research import (
    AnalyzeCapitalFlowHandler,
    AnalyzeFundamentalsHandler,
)
from ai_trading_agent.domain.ability.factors import DEFAULT_FACTOR_REGISTRY
from ai_trading_agent.domain.aggregate.market import Instrument, Quote
from ai_trading_agent.domain.aggregate.research import analyze_financial_sentiment
from ai_trading_agent.domain.aggregate.strategy import StrategyProfile
from ai_trading_agent.domain.enums.market import Market
from ai_trading_agent.infrastructure.config.providers import (
    AShareQuoteFailoverSettings,
    FutuSettings,
    ProviderConfigurationError,
    TencentQuoteSettings,
    TushareSettings,
)
from ai_trading_agent.infrastructure.repo.strategies import SqlAlchemyStrategyProfileRepository
from ai_trading_agent.infrastructure.rpc.akshare_news import AkshareNewsProvider
from ai_trading_agent.infrastructure.rpc.futu_market import FutuMarketDataProvider
from ai_trading_agent.infrastructure.rpc.tencent_market import TencentQuoteMarketDataProvider
from ai_trading_agent.infrastructure.rpc.tushare_market import TushareMarketDataProvider
from ai_trading_agent.infrastructure.rpc.tushare_research import TushareResearchProvider
from ai_trading_agent.interfaces.adapter.environment import load_runtime_environment
from ai_trading_agent.interfaces.facade.persistence import private_session_factory
from ai_trading_agent.interfaces.model.http import (
    NewsItemResponse,
    QuoteQuery,
    ResearchRequest,
    ResearchResponse,
    StrategyInput,
)


def instrument_from_query(query: QuoteQuery) -> Instrument:
    return Instrument(query.symbol, query.market, query.instrument_type)


_a_share_quote_failover: AShareQuoteFailover | None = None


async def latest_quote(instrument: Instrument) -> Quote:
    load_runtime_environment()
    errors: list[str] = []
    futu_provider: FutuMarketDataProvider | None = None
    try:
        futu_provider = FutuMarketDataProvider(FutuSettings.from_environment())
    except ProviderConfigurationError as error:
        errors.append(str(error))

    if instrument.market is Market.A_SHARE:
        tencent_provider = TencentQuoteMarketDataProvider(TencentQuoteSettings.from_environment())
        tushare_provider: TushareMarketDataProvider | None = None
        try:
            tushare_provider = TushareMarketDataProvider(TushareSettings.from_environment())
        except ProviderConfigurationError as error:
            errors.append(str(error))

        if futu_provider:
            return await _get_a_share_quote(
                futu_provider,
                tencent_provider,
                tuple(provider for provider in (tushare_provider,) if provider is not None),
                instrument,
            )
        for provider in (tencent_provider, tushare_provider):
            if provider is None:
                continue
            try:
                return await get_single_quote(provider, instrument)
            except Exception as error:
                errors.append(f"{provider.name}: {error}")
        raise RuntimeError("; ".join(errors) or "no configured provider supports this market")

    if futu_provider:
        try:
            return await get_single_quote(futu_provider, instrument)
        except Exception as error:
            errors.append(f"{futu_provider.name}: {error}")
    detail = "; ".join(errors) or "no configured provider supports this market"
    raise RuntimeError(detail)


async def _get_a_share_quote(
    futu_provider: FutuMarketDataProvider,
    tencent_provider: TencentQuoteMarketDataProvider,
    secondary_fallbacks: tuple[TushareMarketDataProvider, ...],
    instrument: Instrument,
) -> Quote:
    global _a_share_quote_failover
    if _a_share_quote_failover is None:
        settings = AShareQuoteFailoverSettings.from_environment()
        _a_share_quote_failover = AShareQuoteFailover(
            primary=futu_provider,
            fallback=tencent_provider,
            secondary_fallbacks=secondary_fallbacks,
            primary_timeout_seconds=settings.futu_timeout_seconds,
            cooldown_seconds=settings.futu_cooldown_seconds,
        )
    return await _a_share_quote_failover.get_latest_quote(instrument)


async def latest_news(sources: list[str]) -> list[NewsItemResponse]:
    articles = await CollectLatestNewsHandler(AkshareNewsProvider()).handle(
        sources=tuple(source.strip() for source in sources if source.strip()),
        lookback=timedelta(hours=24),
    )
    results: list[NewsItemResponse] = []
    for article in articles[:30]:
        sentiment = analyze_financial_sentiment(f"{article.title}\n{article.content}")
        results.append(
            NewsItemResponse(
                title=article.title,
                content=article.content,
                publisher=article.publisher,
                published_at=article.published_at.isoformat(),
                url=article.url,
                sentiment=sentiment.label,
                sentiment_score=sentiment.score,
            )
        )
    return results


async def research(query: ResearchRequest) -> ResearchResponse:
    instrument = instrument_from_query(query)
    notices: list[str] = []
    fundamentals: dict[str, object] | None = None
    capital_flow: dict[str, object] | None = None
    news_sentiment: dict[str, object] | None = None
    if instrument.market is Market.A_SHARE:
        try:
            load_runtime_environment()
            provider = TushareResearchProvider(TushareSettings.from_environment())
            fundamental = await AnalyzeFundamentalsHandler(provider).handle(instrument)
            fundamentals = {
                "score": fundamental.score,
                "observations": list(fundamental.observations),
                "announced_on": fundamental.snapshot.announced_on.isoformat(),
                "source": fundamental.snapshot.source,
            }
            flow = await AnalyzeCapitalFlowHandler(provider).handle(instrument)
            capital_flow = {
                "trade_date": flow.snapshot.trade_date.isoformat(),
                "net_flow_cny": flow.snapshot.net_flow_cny,
                "large_order_net_flow_cny": flow.snapshot.large_order_net_flow_cny,
                "direction": flow.direction,
                "institutional_direction": flow.institutional_direction,
                "source": flow.snapshot.source,
            }
        except Exception as error:
            notices.append(f"A股基本面/资金流暂不可用：{error}")
    else:
        notices.append("当前基本面与资金流适配器仅覆盖 A 股；港股/美股将显示行情与资讯。")
    try:
        news = await latest_news(query.news_sources)
        text = "\n".join(f"{item.title}\n{item.content}" for item in news)
        if text:
            sentiment = analyze_financial_sentiment(text)
            news_sentiment = {
                "label": sentiment.label,
                "score": sentiment.score,
                "articles": len(news),
                "positive_terms": list(sentiment.positive_terms),
                "negative_terms": list(sentiment.negative_terms),
            }
    except Exception as error:
        notices.append(f"财经资讯情绪暂不可用：{error}")
    return ResearchResponse(
        symbol=instrument.symbol,
        market=instrument.market,
        fundamentals=fundamentals,
        capital_flow=capital_flow,
        news_sentiment=news_sentiment,
        notices=notices,
    )


def strategy_repository(app: FastAPI) -> SqlAlchemyStrategyProfileRepository:
    return SqlAlchemyStrategyProfileRepository(private_session_factory(app))


async def get_strategy(app: FastAPI, strategy_id: UUID) -> StrategyProfile | None:
    return await strategy_repository(app).get(str(strategy_id))


def strategy_from_input(payload: StrategyInput, strategy_id: UUID, version: int) -> StrategyProfile:
    known = {item.identifier for item in DEFAULT_FACTOR_REGISTRY.list()}
    unknown = set(payload.factor_ids) - known
    if unknown:
        raise ValueError(f"unknown factor ids: {', '.join(sorted(unknown))}")
    return StrategyProfile(
        strategy_id=strategy_id,
        name=payload.name,
        thesis=payload.thesis,
        factor_ids=tuple(payload.factor_ids),
        markets=tuple(payload.markets),
        max_position_pct=payload.max_position_pct,
        risk_notes=payload.risk_notes,
        status=payload.status,
        version=version,
    )
