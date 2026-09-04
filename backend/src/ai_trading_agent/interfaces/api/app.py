"""FastAPI delivery routes for the research-agent interface."""

from __future__ import annotations

from uuid import UUID, uuid4

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from ai_trading_agent.application.disciplines import (
    ListDisciplinesHandler,
    SaveDisciplineHandler,
)
from ai_trading_agent.application.factors import GetFactorHandler, ListFactorsHandler
from ai_trading_agent.application.strategies import ListStrategiesHandler, SaveStrategyHandler
from ai_trading_agent.domain.enums.candidates import CandidateRanking
from ai_trading_agent.domain.enums.market import Market
from ai_trading_agent.infrastructure.config.news import OpenAICompatibleLLMSettings
from ai_trading_agent.infrastructure.rpc.llm_advisor import OpenAICompatibleResearchAdvisor
from ai_trading_agent.interfaces.adapter.environment import load_runtime_environment
from ai_trading_agent.interfaces.facade.disciplines import (
    discipline_from_input,
    discipline_repository,
    get_discipline,
)
from ai_trading_agent.interfaces.facade.research_workspace import (
    get_strategy,
    instrument_from_query,
    latest_news,
    latest_quote,
    research,
    strategy_from_input,
    strategy_repository,
    today_candidates,
)
from ai_trading_agent.interfaces.model.http import (
    DEFAULT_NEWS_SOURCES,
    CandidateResponse,
    CandidateScreenResponse,
    ChatRequest,
    ChatResponse,
    DisciplineInput,
    DisciplineResponse,
    FactorResponse,
    NewsItemResponse,
    QuoteQuery,
    QuoteResponse,
    ResearchRequest,
    ResearchResponse,
    StrategyInput,
    StrategyResponse,
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
            return QuoteResponse.from_domain(await latest_quote(instrument_from_query(query)))
        except Exception as error:
            raise HTTPException(status_code=503, detail=f"行情不可用：{error}") from error

    @app.get(
        "/api/v1/market/candidates",
        response_model=CandidateScreenResponse,
        tags=["market"],
    )
    async def get_market_candidates(
        market: Market,
        ranking: CandidateRanking = CandidateRanking.COMPOSITE,
        refresh: bool = False,
    ) -> CandidateScreenResponse:
        try:
            screen, refreshed_at = await today_candidates(market, ranking, refresh=refresh)
            return CandidateScreenResponse(
                market=market,
                ranking=ranking,
                candidates=[CandidateResponse.from_domain(item) for item in screen.candidates],
                universe_size=screen.universe_size,
                refreshed_at=refreshed_at.isoformat(),
                source="tencent_public",
                coverage=(
                    "已筛选腾讯公开行情中的预设高流动性股票研究样本，"
                    "并非全市场扫描；不包含逐股基本面、资金流、期权或关联新闻。"
                ),
                disclaimer="候选仅用于研究与复核，不构成买入、卖出或自动交易指令。",
            )
        except Exception as error:
            raise HTTPException(status_code=503, detail=f"今日研究候选不可用：{error}") from error

    @app.get("/api/v1/news", response_model=list[NewsItemResponse], tags=["news"])
    async def get_news(
        source: tuple[str, ...] = DEFAULT_NEWS_SOURCES,
    ) -> list[NewsItemResponse]:
        try:
            return await latest_news(list(source))
        except Exception as error:
            raise HTTPException(status_code=503, detail=f"财经资讯不可用：{error}") from error

    @app.post("/api/v1/research", response_model=ResearchResponse, tags=["research"])
    async def analyze_research(query: ResearchRequest) -> ResearchResponse:
        return await research(query)

    @app.get("/api/v1/strategies", response_model=list[StrategyResponse], tags=["strategies"])
    async def list_strategies() -> list[StrategyResponse]:
        try:
            profiles = await ListStrategiesHandler(strategy_repository(app)).handle()
            return [StrategyResponse.from_domain(profile) for profile in profiles]
        except Exception as error:
            raise HTTPException(status_code=503, detail=f"策略库不可用：{error}") from error

    @app.post("/api/v1/strategies", response_model=StrategyResponse, tags=["strategies"])
    async def create_strategy(payload: StrategyInput) -> StrategyResponse:
        try:
            profile = strategy_from_input(payload, uuid4(), 1)
            saved = await SaveStrategyHandler(strategy_repository(app)).handle(profile)
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
            current = await get_strategy(app, strategy_id)
            if current is None:
                raise HTTPException(status_code=404, detail="strategy not found")
            profile = strategy_from_input(payload, strategy_id, current.version + 1)
            saved = await SaveStrategyHandler(strategy_repository(app)).handle(profile)
            return StrategyResponse.from_domain(saved)
        except HTTPException:
            raise
        except ValueError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
        except Exception as error:
            raise HTTPException(status_code=503, detail=f"策略保存失败：{error}") from error

    @app.get(
        "/api/v1/disciplines",
        response_model=list[DisciplineResponse],
        tags=["disciplines"],
    )
    async def list_disciplines() -> list[DisciplineResponse]:
        try:
            disciplines = await ListDisciplinesHandler(discipline_repository(app)).handle()
            return [DisciplineResponse.from_domain(item) for item in disciplines]
        except Exception as error:
            raise HTTPException(status_code=503, detail=f"个人纪律库不可用：{error}") from error

    @app.post(
        "/api/v1/disciplines",
        response_model=DisciplineResponse,
        tags=["disciplines"],
    )
    async def create_discipline(payload: DisciplineInput) -> DisciplineResponse:
        try:
            discipline = discipline_from_input(payload, uuid4(), 1)
            saved = await SaveDisciplineHandler(discipline_repository(app)).handle(discipline)
            return DisciplineResponse.from_domain(saved)
        except ValueError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
        except Exception as error:
            raise HTTPException(status_code=503, detail=f"个人纪律保存失败：{error}") from error

    @app.put(
        "/api/v1/disciplines/{discipline_id}",
        response_model=DisciplineResponse,
        tags=["disciplines"],
    )
    async def update_discipline(
        discipline_id: UUID,
        payload: DisciplineInput,
    ) -> DisciplineResponse:
        try:
            current = await get_discipline(app, discipline_id)
            if current is None:
                raise HTTPException(status_code=404, detail="discipline not found")
            discipline = discipline_from_input(payload, discipline_id, current.version + 1)
            saved = await SaveDisciplineHandler(discipline_repository(app)).handle(discipline)
            return DisciplineResponse.from_domain(saved)
        except HTTPException:
            raise
        except ValueError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
        except Exception as error:
            raise HTTPException(status_code=503, detail=f"个人纪律保存失败：{error}") from error

    @app.post("/api/v1/assistant/chat", response_model=ChatResponse, tags=["assistant"])
    async def chat_with_research_agent(request: ChatRequest) -> ChatResponse:
        statuses: list[str] = []
        context: list[str] = []
        if request.symbol and request.market:
            query = QuoteQuery(symbol=request.symbol, market=request.market)
            try:
                quote = await latest_quote(instrument_from_query(query))
                context.append(
                    f"Quote: {quote.instrument.symbol} {quote.last_price} "
                    f"{quote.instrument.currency}; "
                    f"observed_at={quote.observed_at.isoformat()}; source={quote.source}."
                )
                statuses.append("已获取行情")
            except Exception as error:
                statuses.append(f"行情不可用：{error}")
            report = await research(
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
            news = await latest_news(request.news_sources)
            headlines = "\n".join(f"- {item.title} ({item.publisher})" for item in news[:8])
            context.append(f"Recent financial news:\n{headlines}")
            statuses.append("已获取财经资讯")
        except Exception as error:
            statuses.append(f"资讯不可用：{error}")
        if request.strategy_id:
            try:
                strategy = await get_strategy(app, request.strategy_id)
                if strategy is None:
                    statuses.append("所选策略不存在")
                else:
                    context.append(f"User strategy preference: {strategy.definition()}")
                    statuses.append(f"已注入策略：{strategy.name}")
            except Exception as error:
                statuses.append(f"策略不可用：{error}")
        try:
            load_runtime_environment()
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
