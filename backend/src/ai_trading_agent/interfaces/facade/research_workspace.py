"""Interface-level orchestration for market, news, research and strategy workspaces."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import UUID

from fastapi import FastAPI

from ai_trading_agent.application.a_share_quote_failover import (
    AShareQuoteFailover,
    get_single_quote,
)
from ai_trading_agent.application.candidates import (
    CandidateScreen,
    RankMarketCandidates,
    RankMarketCandidatesHandler,
)
from ai_trading_agent.application.funds import GetFundResearchHandler
from ai_trading_agent.application.market_scans import (
    GetLatestMarketScanHandler,
    PurgeExpiredMarketDataHandler,
    RunMarketScanHandler,
)
from ai_trading_agent.application.news import ResilientLatestNewsHandler
from ai_trading_agent.application.ports import MarketDataProvider
from ai_trading_agent.application.research import (
    AnalyzeCapitalFlowHandler,
    AnalyzeFundamentalsHandler,
)
from ai_trading_agent.application.technical import (
    AnalyzeTechnicalStudyHandler,
    HistoricalBarsProvider,
)
from ai_trading_agent.application.watchlist_detail import GetWatchlistFinancialDetailHandler
from ai_trading_agent.domain.ability.factors import DEFAULT_FACTOR_REGISTRY
from ai_trading_agent.domain.aggregate.fund import FundResearchReport
from ai_trading_agent.domain.aggregate.market import Instrument, Quote
from ai_trading_agent.domain.aggregate.research import (
    FinancialSnapshot,
    analyze_financial_sentiment,
)
from ai_trading_agent.domain.aggregate.strategy import StrategyProfile
from ai_trading_agent.domain.aggregate.technical import PriceBar
from ai_trading_agent.domain.aggregate.watchlist_detail import WatchlistFinancialDetail
from ai_trading_agent.domain.enums.candidates import CandidateRanking
from ai_trading_agent.domain.enums.market import InstrumentType, Market
from ai_trading_agent.domain.service.factor_analysis import analyze_builtin_factors
from ai_trading_agent.infrastructure.config.providers import (
    AShareQuoteFailoverSettings,
    FutuSettings,
    HithinkFinanceSettings,
    MarketScanSettings,
    ProviderConfigurationError,
    TencentQuoteSettings,
    TushareSettings,
)
from ai_trading_agent.infrastructure.repo.market_scans import SqlAlchemyMarketScanRepository
from ai_trading_agent.infrastructure.repo.strategies import SqlAlchemyStrategyProfileRepository
from ai_trading_agent.infrastructure.rpc.akshare_news import AkshareNewsProvider
from ai_trading_agent.infrastructure.rpc.futu_market import FutuMarketDataProvider
from ai_trading_agent.infrastructure.rpc.futu_scanner import FutuMarketScanner
from ai_trading_agent.infrastructure.rpc.historical_bars import (
    FutuHistoricalBarsProvider,
    HithinkAshareHistoricalBarsProvider,
)
from ai_trading_agent.infrastructure.rpc.hithink_funds import (
    HithinkFundHistoricalBarsProvider,
    HithinkFundMarketDataProvider,
    HithinkFundResearchProvider,
)
from ai_trading_agent.infrastructure.rpc.hithink_market import (
    HithinkFinanceMarketDataProvider,
)
from ai_trading_agent.infrastructure.rpc.hithink_research import HithinkAshareResearchProvider
from ai_trading_agent.infrastructure.rpc.hithink_valuations import HithinkAshareValuationProvider
from ai_trading_agent.infrastructure.rpc.hithink_watchlist_detail import (
    HithinkWatchlistDetailProvider,
)
from ai_trading_agent.infrastructure.rpc.tencent_market import TencentQuoteMarketDataProvider
from ai_trading_agent.infrastructure.rpc.tushare_market import TushareMarketDataProvider
from ai_trading_agent.infrastructure.rpc.tushare_research import TushareResearchProvider
from ai_trading_agent.infrastructure.rpc.tushare_scanner import TushareMarketScanner
from ai_trading_agent.interfaces.adapter.environment import load_runtime_environment
from ai_trading_agent.interfaces.facade.persistence import private_session_factory
from ai_trading_agent.interfaces.model.http import (
    NewsItemResponse,
    QuoteQuery,
    ResearchRequest,
    ResearchResponse,
    StrategyInput,
    TechnicalRequest,
    TechnicalResponse,
)


def instrument_from_query(query: QuoteQuery) -> Instrument:
    return Instrument(query.symbol, query.market, query.instrument_type)


_a_share_quote_failover: AShareQuoteFailover | None = None
_candidate_screen_cache: dict[
    tuple[Market, CandidateRanking], tuple[datetime, CandidateScreen]
] = {}
_CANDIDATE_CACHE_TTL = timedelta(minutes=5)
_news_collector = ResilientLatestNewsHandler(AkshareNewsProvider())


async def latest_quote(instrument: Instrument) -> Quote:
    load_runtime_environment()
    errors: list[str] = []
    futu_provider: FutuMarketDataProvider | None = None
    try:
        futu_provider = FutuMarketDataProvider(FutuSettings.from_environment())
    except ProviderConfigurationError as error:
        errors.append(str(error))

    if _is_hithink_fund(instrument):
        try:
            provider = HithinkFundMarketDataProvider(HithinkFinanceSettings.from_environment())
            return await get_single_quote(provider, instrument)
        except Exception as error:
            errors.append(f"hithink_finance_fund: {error}")
            if instrument.market is Market.FUND:
                raise RuntimeError("; ".join(errors)) from error

    if instrument.market is Market.A_SHARE:
        tencent_provider = TencentQuoteMarketDataProvider(TencentQuoteSettings.from_environment())
        hithink_provider: HithinkFinanceMarketDataProvider | None = None
        try:
            hithink_provider = HithinkFinanceMarketDataProvider(
                HithinkFinanceSettings.from_environment()
            )
        except ProviderConfigurationError as error:
            errors.append(str(error))
        tushare_provider: TushareMarketDataProvider | None = None
        try:
            tushare_provider = TushareMarketDataProvider(TushareSettings.from_environment())
        except ProviderConfigurationError as error:
            errors.append(str(error))

        if futu_provider:
            return await _get_a_share_quote(
                futu_provider,
                hithink_provider or tencent_provider,
                tuple(
                    provider
                    for provider in (tencent_provider, tushare_provider)
                    if provider is not hithink_provider and provider is not None
                ),
                instrument,
            )
        for provider in (hithink_provider, tencent_provider, tushare_provider):
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
    fallback_provider: MarketDataProvider,
    secondary_fallbacks: tuple[MarketDataProvider, ...],
    instrument: Instrument,
) -> Quote:
    global _a_share_quote_failover
    if _a_share_quote_failover is None:
        settings = AShareQuoteFailoverSettings.from_environment()
        _a_share_quote_failover = AShareQuoteFailover(
            primary=futu_provider,
            fallback=fallback_provider,
            secondary_fallbacks=secondary_fallbacks,
            primary_timeout_seconds=settings.futu_timeout_seconds,
            cooldown_seconds=settings.futu_cooldown_seconds,
        )
    return await _a_share_quote_failover.get_latest_quote(instrument)


async def latest_news(sources: list[str]) -> list[NewsItemResponse]:
    articles = await _news_collector.handle(
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


async def today_candidates(
    market: Market,
    ranking: CandidateRanking,
    *,
    refresh: bool = False,
) -> tuple[CandidateScreen, datetime]:
    """Return a short-lived public-data candidate screen for one market."""
    key = (market, ranking)
    now = datetime.now(UTC)
    cached = _candidate_screen_cache.get(key)
    if not refresh and cached is not None and now - cached[0] < _CANDIDATE_CACHE_TTL:
        return cached[1], cached[0]

    provider = TencentQuoteMarketDataProvider(TencentQuoteSettings.from_environment())
    screen = await RankMarketCandidatesHandler(provider).handle(
        RankMarketCandidates(market=market, ranking=ranking)
    )
    _candidate_screen_cache[key] = (screen, now)
    return screen, now


async def run_market_scan(
    app: FastAPI,
    market: Market,
    *,
    purge_after_scan: bool = True,
):  # type: ignore[no-untyped-def]
    """Compose one market scanner and persist its run without exposing secrets."""
    load_runtime_environment()
    settings = MarketScanSettings.from_environment()
    if market is Market.A_SHARE:
        provider = TushareMarketScanner(TushareSettings.from_environment())
    else:
        provider = FutuMarketScanner(FutuSettings.from_environment(), settings)
    repository = SqlAlchemyMarketScanRepository(private_session_factory(app))
    run = await RunMarketScanHandler(provider, repository).handle(market)
    if purge_after_scan:
        await PurgeExpiredMarketDataHandler(repository).handle()
    return run


async def latest_market_scan(app: FastAPI, market: Market):  # type: ignore[no-untyped-def]
    repository = SqlAlchemyMarketScanRepository(private_session_factory(app))
    return await GetLatestMarketScanHandler(repository).handle(market)


async def run_scheduled_market_scans(app: FastAPI) -> None:
    for market in Market:
        await run_market_scan(app, market, purge_after_scan=False)
    repository = SqlAlchemyMarketScanRepository(private_session_factory(app))
    await PurgeExpiredMarketDataHandler(repository).handle()


async def research(query: ResearchRequest) -> ResearchResponse:
    instrument = instrument_from_query(query)
    notices: list[str] = []
    fundamentals: dict[str, object] | None = None
    capital_flow: dict[str, object] | None = None
    news_sentiment: dict[str, object] | None = None
    fund_research: dict[str, object] | None = None
    financial_snapshot: FinancialSnapshot | None = None
    if _is_hithink_fund(instrument):
        try:
            report = await fund_research_report(instrument)
            fund_research = fund_research_payload(report)
            fundamentals = {
                "name": report.overview.name,
                "management_company": report.overview.management_company,
                "manager_name": report.overview.manager_name,
                "fund_scale": report.overview.fund_scale,
                "latest_unit_nav": report.overview.latest_unit_nav,
                "latest_financials": report.latest_financials,
                "source": report.source,
            }
            capital_flow = {
                "asset_allocations": fund_research["asset_allocations"],
                "institutional_holding_percent": report.institutional_holding_percent,
                "holdings": fund_research["holdings"],
                "source": report.source,
            }
            text = "\n".join(f"{article.title}\n{article.summary or ''}" for article in report.news)
            if text:
                sentiment = analyze_financial_sentiment(text)
                news_sentiment = {
                    "label": sentiment.label,
                    "score": sentiment.score,
                    "articles": len(report.news),
                    "positive_terms": list(sentiment.positive_terms),
                    "negative_terms": list(sentiment.negative_terms),
                    "source": report.source,
                }
            notices.extend(report.limitations)
        except Exception as error:
            notices.append(f"基金/ETF 研究暂不可用：{error}")
    elif instrument.market is Market.A_SHARE:
        try:
            load_runtime_environment()
            provider = HithinkAshareResearchProvider(HithinkFinanceSettings.from_environment())
            fundamental = await AnalyzeFundamentalsHandler(provider).handle(instrument)
            financial_snapshot = fundamental.snapshot
            fundamentals = {
                "score": fundamental.score,
                "observations": list(fundamental.observations),
                "announced_on": fundamental.snapshot.announced_on.isoformat(),
                "source": fundamental.snapshot.source,
            }
        except Exception as error:
            notices.append(f"A股基本面暂不可用：{error}")
        try:
            flow_provider = TushareResearchProvider(TushareSettings.from_environment())
            flow = await AnalyzeCapitalFlowHandler(flow_provider).handle(instrument)
            capital_flow = {
                "trade_date": flow.snapshot.trade_date.isoformat(),
                "net_flow_cny": flow.snapshot.net_flow_cny,
                "large_order_net_flow_cny": flow.snapshot.large_order_net_flow_cny,
                "direction": flow.direction,
                "institutional_direction": flow.institutional_direction,
                "source": flow.snapshot.source,
            }
        except Exception as error:
            notices.append(f"A股资金流暂不可用：{error}")
    else:
        notices.append("当前基本面与资金流适配器仅覆盖 A 股；港股/美股将显示行情与资讯。")
    if not _is_hithink_fund(instrument):
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
    factor_analysis = await builtin_factor_analysis(
        instrument,
        financial_snapshot=financial_snapshot,
        news_sentiment=news_sentiment,
    )
    return ResearchResponse(
        symbol=instrument.symbol,
        market=instrument.market,
        fundamentals=fundamentals,
        capital_flow=capital_flow,
        news_sentiment=news_sentiment,
        fund_research=fund_research,
        factor_analysis=factor_analysis,
        notices=notices,
    )


async def builtin_factor_analysis(
    instrument: Instrument,
    *,
    financial_snapshot: FinancialSnapshot | None,
    news_sentiment: dict[str, object] | None,
) -> dict[str, object]:
    """Collect bounded inputs and return the ten-factor analysis without hiding gaps."""
    bars = ()
    technical_source: str | None = None
    notices: list[str] = []
    try:
        load_runtime_environment()
        if _is_exchange_etf(instrument):
            provider = HithinkFundHistoricalBarsProvider(HithinkFinanceSettings.from_environment())
        elif instrument.market is Market.A_SHARE:
            provider = HithinkAshareHistoricalBarsProvider(
                HithinkFinanceSettings.from_environment()
            )
        elif instrument.market is Market.FUND:
            provider = None
        else:
            provider = FutuHistoricalBarsProvider(FutuSettings.from_environment())
        if provider is None:
            notices.append("场外基金暂无真实 OHLCV，价格类因子不可用。")
        else:
            bars = await provider.get_daily_bars(instrument, limit=90)
            technical_source = provider.name
    except Exception as error:
        notices.append(f"日线因子输入暂不可用：{error}")

    pe_ttm = None
    pb_mrq = None
    valuation_source: str | None = None
    if instrument.market is Market.A_SHARE:
        try:
            provider = HithinkAshareValuationProvider(HithinkFinanceSettings.from_environment())
            valuation = await provider.get_valuation_snapshot(instrument)
            pe_ttm = valuation.pe_ttm
            pb_mrq = valuation.pb_mrq
            valuation_source = valuation.source
        except Exception as error:
            notices.append(f"估值因子输入暂不可用：{error}")

    sentiment_score = None
    sentiment_source = None
    if news_sentiment is not None:
        raw_score = news_sentiment.get("score")
        try:
            sentiment_score = Decimal(str(raw_score)) if raw_score is not None else None
        except Exception:
            notices.append("财经资讯情绪分数格式无效。")
        raw_source = news_sentiment.get("source")
        sentiment_source = str(raw_source) if raw_source is not None else "public_financial_news"

    analysis = analyze_builtin_factors(
        instrument,
        bars,
        technical_source=technical_source,
        pe_ttm=pe_ttm,
        pb_mrq=pb_mrq,
        roe_pct=financial_snapshot.return_on_equity_pct if financial_snapshot else None,
        financial_source=(financial_snapshot.source if financial_snapshot else valuation_source),
        news_sentiment=sentiment_score,
        news_source=sentiment_source,
    )
    return {
        "observed_at": analysis.observed_at.isoformat(),
        "available_count": analysis.available_count,
        "total_count": len(analysis.observations),
        "supportive_count": analysis.supportive_count,
        "adverse_count": analysis.adverse_count,
        "notices": notices,
        "observations": [
            {
                "identifier": item.identifier,
                "name": item.name,
                "theme": item.theme,
                "value": item.value,
                "unit": item.unit,
                "direction": item.direction,
                "interpretation": item.interpretation,
                "source": item.source,
                "unavailable_reason": item.unavailable_reason,
            }
            for item in analysis.observations
        ],
    }


async def watchlist_financial_detail(instrument: Instrument):  # type: ignore[no-untyped-def]
    """Return published company detail for one selected A-share equity only."""
    if (
        instrument.market is not Market.A_SHARE
        or instrument.instrument_type is not InstrumentType.EQUITY
    ):
        return WatchlistFinancialDetail(
            instrument=instrument,
            observed_at=datetime.now(UTC),
            source="not_applicable",
            income_statement=None,
            balance_sheet=None,
            cash_flow=None,
            valuation=None,
            time_catalysts=(),
            notices=(
                "上市公司财报、A 股估值和除权除息事件仅适用于 A 股股票。"
                "ETF 与基金请查看其已披露的基金持仓、资产配置和净值研究数据。",
            ),
        )
    load_runtime_environment()
    provider = HithinkWatchlistDetailProvider(HithinkFinanceSettings.from_environment())
    return await GetWatchlistFinancialDetailHandler(provider).handle(instrument)


async def technical_study(query: TechnicalRequest) -> TechnicalResponse:
    """Compose source selection at the interface edge, not in the domain."""
    instrument = instrument_from_query(query)
    provider = historical_bars_provider(instrument)
    study = await AnalyzeTechnicalStudyHandler(provider).handle(
        instrument, query.timeframe, limit=query.limit
    )
    return TechnicalResponse(
        symbol=instrument.symbol,
        market=instrument.market,
        currency=instrument.currency,
        timeframe=study.timeframe,
        source=study.source,
        bars=[
            {
                "date": bar.session_date.isoformat(),
                "open": bar.open_price,
                "high": bar.high_price,
                "low": bar.low_price,
                "close": bar.close_price,
                "volume": bar.volume,
            }
            for bar in study.bars
        ],
        indicators={
            "sma_5": study.indicators.sma_5,
            "sma_10": study.indicators.sma_10,
            "sma_20": study.indicators.sma_20,
            "sma_60": study.indicators.sma_60,
            "rsi_14": study.indicators.rsi_14,
            "macd": study.indicators.macd,
            "macd_signal": study.indicators.macd_signal,
            "macd_histogram": study.indicators.macd_histogram,
            "obv": study.indicators.obv,
            "atr_14": study.indicators.atr_14,
        },
        volume_profile={
            "point_of_control": study.volume_profile.point_of_control,
            "value_area_low": study.volume_profile.value_area_low,
            "value_area_high": study.volume_profile.value_area_high,
            "value_area_percent": study.volume_profile.value_area_percent,
            "method": study.volume_profile.method,
            "levels": [
                {"price": level.price, "volume": level.volume, "percent": level.percent_of_volume}
                for level in study.volume_profile.levels
            ],
        },
        assessment={
            "trend": study.assessment.trend,
            "momentum": study.assessment.momentum,
            "volume_pressure": study.assessment.volume_pressure,
            "observations": list(study.assessment.observations),
            "limitations": list(study.assessment.limitations),
        },
    )


async def historical_daily_bars(instrument: Instrument, *, limit: int = 90) -> tuple[PriceBar, ...]:
    """Retrieve daily bars for a focused portfolio metric without full technical analysis."""
    if not 2 <= limit <= 1_200:
        raise ValueError("historical bar limit must be between 2 and 1200")
    return await historical_bars_provider(instrument).get_daily_bars(instrument, limit)


def historical_bars_provider(instrument: Instrument) -> HistoricalBarsProvider:
    """Centralize market-specific OHLCV selection for every focused use case."""
    load_runtime_environment()
    if _is_exchange_etf(instrument):
        return HithinkFundHistoricalBarsProvider(HithinkFinanceSettings.from_environment())
    if instrument.market is Market.FUND:
        raise ValueError(
            "场外基金暂无真实 OHLCV，无法生成 K 线或基于收盘价的月度盈亏；"
            "可使用基金研究页查看净值和回撤。"
        )
    if instrument.market is Market.A_SHARE:
        return HithinkAshareHistoricalBarsProvider(HithinkFinanceSettings.from_environment())
    return FutuHistoricalBarsProvider(FutuSettings.from_environment())


async def fund_research_report(instrument: Instrument) -> FundResearchReport:
    """Resolve one selected public fund into its dedicated disclosed-data aggregate."""
    load_runtime_environment()
    provider = HithinkFundResearchProvider(HithinkFinanceSettings.from_environment())
    return await GetFundResearchHandler(provider).handle(instrument)


def fund_research_payload(report: FundResearchReport) -> dict[str, object]:
    """Translate domain values at the HTTP composition boundary only."""
    return {
        "overview": {
            "name": report.overview.name,
            "management_company": report.overview.management_company,
            "manager_name": report.overview.manager_name,
            "fund_scale": report.overview.fund_scale,
            "latest_unit_nav": report.overview.latest_unit_nav,
        },
        "nav_history": [
            {
                "date": item.nav_date.isoformat(),
                "unit_nav": item.unit_nav,
                "adjusted_nav": item.adjusted_nav,
            }
            for item in report.nav_history
        ],
        "returns_percent": report.returns_percent,
        "drawdowns_percent": report.drawdowns_percent,
        "holdings": [
            {
                "name": item.name,
                "asset_type": item.asset_type,
                "weight_percent": item.weight_percent,
                "market_value": item.market_value,
                "disclosed_at": item.disclosed_at.isoformat() if item.disclosed_at else None,
            }
            for item in report.holdings
        ],
        "asset_allocations": [
            {
                "report_date": item.report_date.isoformat() if item.report_date else None,
                "stock_percent": item.stock_percent,
                "bond_percent": item.bond_percent,
                "cash_percent": item.cash_percent,
                "other_percent": item.other_percent,
            }
            for item in report.allocations
        ],
        "institutional_holding_percent": report.institutional_holding_percent,
        "latest_financials": report.latest_financials,
        "diagnostics": report.diagnostics,
        "news": [
            {
                "title": item.title,
                "summary": item.summary,
                "publisher": item.publisher,
                "url": item.url,
                "published_at": item.published_at.isoformat() if item.published_at else None,
            }
            for item in report.news
        ],
        "limitations": list(report.limitations),
        "source": report.source,
        "observed_at": report.observed_at.isoformat(),
    }


def _is_exchange_etf(instrument: Instrument) -> bool:
    return instrument.market is Market.A_SHARE and instrument.instrument_type is InstrumentType.ETF


def _is_hithink_fund(instrument: Instrument) -> bool:
    return _is_exchange_etf(instrument) or (
        instrument.market is Market.FUND and instrument.instrument_type is InstrumentType.FUND
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
