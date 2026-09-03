"""Versioned HTTP API composition root; all credentials remain server-side."""

from __future__ import annotations

import os
from datetime import timedelta
from decimal import Decimal
from pathlib import Path
from uuid import UUID, uuid4

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, ConfigDict, Field

from ai_trading_agent.application.factors import GetFactorHandler, ListFactorsHandler
from ai_trading_agent.application.news import CollectLatestNewsHandler
from ai_trading_agent.application.research import (
    AnalyzeCapitalFlowHandler,
    AnalyzeFundamentalsHandler,
)
from ai_trading_agent.application.strategies import ListStrategiesHandler, SaveStrategyHandler
from ai_trading_agent.domain.factors import DEFAULT_FACTOR_REGISTRY, FactorMetadata
from ai_trading_agent.domain.market import Instrument, InstrumentType, Market, Quote
from ai_trading_agent.domain.research import analyze_financial_sentiment
from ai_trading_agent.domain.strategy import StrategyProfile
from ai_trading_agent.infrastructure.market_data.config import (
    FutuSettings,
    ProviderConfigurationError,
    TushareSettings,
)
from ai_trading_agent.infrastructure.market_data.futu import FutuMarketDataProvider
from ai_trading_agent.infrastructure.market_data.tushare import TushareMarketDataProvider
from ai_trading_agent.infrastructure.news.advisor import OpenAICompatibleResearchAdvisor
from ai_trading_agent.infrastructure.news.config import OpenAICompatibleLLMSettings
from ai_trading_agent.infrastructure.news.tushare import TushareNewsProvider
from ai_trading_agent.infrastructure.persistence.database import (
    create_database_engine,
    create_session_factory,
)
from ai_trading_agent.infrastructure.persistence.strategies import (
    SqlAlchemyStrategyProfileRepository,
)
from ai_trading_agent.infrastructure.research.tushare import TushareResearchProvider

DEFAULT_NEWS_SOURCES = ("sina",)


class FactorResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    identifier: str
    name: str
    theme: str
    formula: str
    columns_required: tuple[str, ...]
    warmup_bars: int
    horizon_days: int
    description: str
    version: str

    @classmethod
    def from_domain(cls, factor: FactorMetadata) -> FactorResponse:
        return cls.model_validate(factor)


class QuoteQuery(BaseModel):
    symbol: str = Field(min_length=1, max_length=64)
    market: Market
    instrument_type: InstrumentType = InstrumentType.EQUITY


class QuoteResponse(BaseModel):
    symbol: str
    market: Market
    currency: str
    last_price: Decimal
    observed_at: str
    source: str
    open_price: Decimal | None
    high_price: Decimal | None
    low_price: Decimal | None
    previous_close: Decimal | None
    volume: Decimal | None

    @classmethod
    def from_domain(cls, quote: Quote) -> QuoteResponse:
        return cls(
            symbol=quote.instrument.symbol,
            market=quote.instrument.market,
            currency=quote.instrument.currency,
            last_price=quote.last_price,
            observed_at=quote.observed_at.isoformat(),
            source=quote.source,
            open_price=quote.open_price,
            high_price=quote.high_price,
            low_price=quote.low_price,
            previous_close=quote.previous_close,
            volume=quote.volume,
        )


class NewsItemResponse(BaseModel):
    title: str
    content: str
    publisher: str
    published_at: str
    url: str | None
    sentiment: str
    sentiment_score: Decimal


class ResearchRequest(QuoteQuery):
    news_sources: list[str] = Field(
        default_factory=lambda: list(DEFAULT_NEWS_SOURCES), max_length=5
    )


class ResearchResponse(BaseModel):
    symbol: str
    market: Market
    fundamentals: dict[str, object] | None
    capital_flow: dict[str, object] | None
    news_sentiment: dict[str, object] | None
    notices: list[str]


class StrategyInput(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    thesis: str = Field(min_length=1, max_length=8_000)
    factor_ids: list[str] = Field(min_length=1, max_length=20)
    markets: list[Market] = Field(min_length=1, max_length=3)
    max_position_pct: Decimal = Field(gt=0, le=100)
    risk_notes: str = Field(default="", max_length=4_000)
    status: str = Field(default="draft", pattern="^(draft|active|archived)$")


class StrategyResponse(StrategyInput):
    strategy_id: UUID
    version: int

    @classmethod
    def from_domain(cls, profile: StrategyProfile) -> StrategyResponse:
        return cls(
            strategy_id=profile.strategy_id,
            name=profile.name,
            thesis=profile.thesis,
            factor_ids=list(profile.factor_ids),
            markets=list(profile.markets),
            max_position_pct=profile.max_position_pct,
            risk_notes=profile.risk_notes,
            status=profile.status,
            version=profile.version,
        )


class ChatRequest(BaseModel):
    question: str = Field(min_length=1, max_length=8_000)
    symbol: str | None = Field(default=None, max_length=64)
    market: Market | None = None
    strategy_id: UUID | None = None
    news_sources: list[str] = Field(
        default_factory=lambda: list(DEFAULT_NEWS_SOURCES), max_length=5
    )


class ChatResponse(BaseModel):
    answer: str
    context_status: list[str]
    disclaimer: str


def _load_runtime_environment() -> None:
    """Load user-managed config only within the running backend process."""
    root_env = Path(__file__).resolve().parents[5] / ".env"
    backend_env = Path.cwd() / ".env"
    load_dotenv(root_env, override=False)
    load_dotenv(backend_env, override=False)


def _instrument(query: QuoteQuery) -> Instrument:
    return Instrument(query.symbol, query.market, query.instrument_type)


async def _latest_quote(instrument: Instrument) -> Quote:
    _load_runtime_environment()
    providers = []
    errors: list[str] = []
    try:
        providers.append(FutuMarketDataProvider(FutuSettings.from_environment()))
    except ProviderConfigurationError as error:
        errors.append(str(error))
    if instrument.market is Market.A_SHARE:
        try:
            providers.append(TushareMarketDataProvider(TushareSettings.from_environment()))
        except ProviderConfigurationError as error:
            errors.append(str(error))
    for provider in providers:
        if not provider.supports(instrument.market):
            continue
        try:
            quotes = await provider.get_latest_quotes([instrument])
            if len(quotes) == 1:
                return quotes[0]
        except Exception as error:
            errors.append(f"{provider.name}: {error}")
    detail = "; ".join(errors) or "no configured provider supports this market"
    raise RuntimeError(detail)


async def _latest_news(sources: list[str]) -> list[NewsItemResponse]:
    _load_runtime_environment()
    provider = TushareNewsProvider(TushareSettings.from_environment())
    articles = await CollectLatestNewsHandler(provider).handle(
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


async def _research(query: ResearchRequest) -> ResearchResponse:
    instrument = _instrument(query)
    notices: list[str] = []
    fundamentals: dict[str, object] | None = None
    capital_flow: dict[str, object] | None = None
    news_sentiment: dict[str, object] | None = None
    if instrument.market is Market.A_SHARE:
        try:
            _load_runtime_environment()
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
        news = await _latest_news(query.news_sources)
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


def _strategy_repository(app: FastAPI) -> SqlAlchemyStrategyProfileRepository:
    repository = getattr(app.state, "strategy_repository", None)
    if repository is not None:
        return repository
    _load_runtime_environment()
    database_url = os.environ.get("DATABASE_URL", "").strip()
    if not database_url:
        raise RuntimeError("DATABASE_URL is required to save personal strategies")
    app.state.database_engine = create_database_engine(database_url)
    sessions = create_session_factory(app.state.database_engine)
    repository = SqlAlchemyStrategyProfileRepository(sessions)
    app.state.strategy_repository = repository
    return repository


async def _get_strategy(app: FastAPI, strategy_id: UUID) -> StrategyProfile | None:
    return await _strategy_repository(app).get(str(strategy_id))


def _strategy_from_input(
    payload: StrategyInput, strategy_id: UUID, version: int
) -> StrategyProfile:
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


def create_app(*, cors_origins: tuple[str, ...] = ()) -> FastAPI:
    app = FastAPI(title="My AI Trading Agent API", version="0.2.0")
    if cors_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=list(cors_origins),
            allow_credentials=True,
            allow_methods=["GET", "POST", "PUT", "DELETE"],
            allow_headers=["Authorization", "Content-Type"],
        )
    list_factors = ListFactorsHandler()
    get_factor = GetFactorHandler()

    @app.get("/healthz", tags=["system"])
    def healthcheck() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/api/v1/factors", response_model=list[FactorResponse], tags=["factors"])
    def list_factor_library() -> list[FactorResponse]:
        return [FactorResponse.from_domain(item) for item in list_factors.handle()]

    @app.get("/api/v1/factors/{identifier}", response_model=FactorResponse, tags=["factors"])
    def get_factor_definition(identifier: str) -> FactorResponse:
        try:
            return FactorResponse.from_domain(get_factor.handle(identifier))
        except KeyError as error:
            raise HTTPException(status_code=404, detail="factor not found") from error

    @app.post("/api/v1/market/quote", response_model=QuoteResponse, tags=["market"])
    async def get_market_quote(query: QuoteQuery) -> QuoteResponse:
        try:
            return QuoteResponse.from_domain(await _latest_quote(_instrument(query)))
        except Exception as error:
            raise HTTPException(status_code=503, detail=f"行情不可用：{error}") from error

    @app.get("/api/v1/news", response_model=list[NewsItemResponse], tags=["news"])
    async def get_news(
        source: tuple[str, ...] = DEFAULT_NEWS_SOURCES,
    ) -> list[NewsItemResponse]:
        try:
            return await _latest_news(list(source))
        except Exception as error:
            raise HTTPException(status_code=503, detail=f"财经资讯不可用：{error}") from error

    @app.post("/api/v1/research", response_model=ResearchResponse, tags=["research"])
    async def analyze_research(query: ResearchRequest) -> ResearchResponse:
        return await _research(query)

    @app.get("/api/v1/strategies", response_model=list[StrategyResponse], tags=["strategies"])
    async def list_strategies() -> list[StrategyResponse]:
        try:
            profiles = await ListStrategiesHandler(_strategy_repository(app)).handle()
            return [StrategyResponse.from_domain(profile) for profile in profiles]
        except Exception as error:
            raise HTTPException(status_code=503, detail=f"策略库不可用：{error}") from error

    @app.post("/api/v1/strategies", response_model=StrategyResponse, tags=["strategies"])
    async def create_strategy(payload: StrategyInput) -> StrategyResponse:
        try:
            profile = _strategy_from_input(payload, uuid4(), 1)
            saved = await SaveStrategyHandler(_strategy_repository(app)).handle(profile)
            return StrategyResponse.from_domain(saved)
        except ValueError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
        except Exception as error:
            raise HTTPException(status_code=503, detail=f"策略保存失败：{error}") from error

    @app.put(
        "/api/v1/strategies/{strategy_id}", response_model=StrategyResponse, tags=["strategies"]
    )
    async def update_strategy(strategy_id: UUID, payload: StrategyInput) -> StrategyResponse:
        try:
            current = await _get_strategy(app, strategy_id)
            if current is None:
                raise HTTPException(status_code=404, detail="strategy not found")
            profile = _strategy_from_input(payload, strategy_id, current.version + 1)
            saved = await SaveStrategyHandler(_strategy_repository(app)).handle(profile)
            return StrategyResponse.from_domain(saved)
        except HTTPException:
            raise
        except ValueError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
        except Exception as error:
            raise HTTPException(status_code=503, detail=f"策略保存失败：{error}") from error

    @app.post("/api/v1/assistant/chat", response_model=ChatResponse, tags=["assistant"])
    async def chat_with_research_agent(request: ChatRequest) -> ChatResponse:
        statuses: list[str] = []
        context: list[str] = []
        if request.symbol and request.market:
            query = QuoteQuery(symbol=request.symbol, market=request.market)
            try:
                quote = await _latest_quote(_instrument(query))
                context.append(
                    f"Quote: {quote.instrument.symbol} {quote.last_price} "
                    f"{quote.instrument.currency}; "
                    f"observed_at={quote.observed_at.isoformat()}; source={quote.source}."
                )
                statuses.append("已获取行情")
            except Exception as error:
                statuses.append(f"行情不可用：{error}")
            report = await _research(
                ResearchRequest(
                    symbol=request.symbol,
                    market=request.market,
                    news_sources=request.news_sources,
                )
            )
            context.append(f"Research: {report.model_dump_json()}")
            statuses.append("已汇总研究分析")
        else:
            statuses.append("未指定标的；仅按问题与策略回答")
        try:
            news = await _latest_news(request.news_sources)
            headlines = "\n".join(f"- {item.title} ({item.publisher})" for item in news[:8])
            context.append(f"Recent financial news:\n{headlines}")
            statuses.append("已获取财经资讯")
        except Exception as error:
            statuses.append(f"资讯不可用：{error}")
        if request.strategy_id:
            try:
                strategy = await _get_strategy(app, request.strategy_id)
                if strategy is None:
                    statuses.append("所选策略不存在")
                else:
                    context.append(f"User strategy preference: {strategy.definition()}")
                    statuses.append(f"已注入策略：{strategy.name}")
            except Exception as error:
                statuses.append(f"策略不可用：{error}")
        try:
            _load_runtime_environment()
            adviser = OpenAICompatibleResearchAdvisor(
                OpenAICompatibleLLMSettings.from_environment()
            )
            answer = await adviser.answer(question=request.question, context="\n\n".join(context))
        except Exception as error:
            raise HTTPException(status_code=503, detail=f"AI 研究助手不可用：{error}") from error
        return ChatResponse(
            answer=answer,
            context_status=statuses,
            disclaimer="研究结果仅供信息与研究参考，不构成投资或交易指令。",
        )

    return app


app = create_app()
