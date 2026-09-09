"""FastAPI delivery routes for the research-agent interface."""

from __future__ import annotations

from contextlib import asynccontextmanager
from uuid import UUID, uuid4

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from ai_trading_agent.application.disciplines import (
    ListDisciplinesHandler,
    SaveDisciplineHandler,
)
from ai_trading_agent.application.factors import GetFactorHandler, ListFactorsHandler
from ai_trading_agent.application.portfolio import (
    ListPaperPositionsHandler,
    ListWatchlistHandler,
    SavePaperPositionHandler,
    SaveWatchlistHandler,
)
from ai_trading_agent.application.strategies import ListStrategiesHandler, SaveStrategyHandler
from ai_trading_agent.domain.aggregate.watchlist import value_paper_position
from ai_trading_agent.domain.enums.candidates import CandidateRanking
from ai_trading_agent.domain.enums.market import Market
from ai_trading_agent.infrastructure.config.news import OpenAICompatibleLLMSettings
from ai_trading_agent.infrastructure.rpc.llm_advisor import OpenAICompatibleResearchAdvisor
from ai_trading_agent.interfaces.adapter.environment import load_runtime_environment
from ai_trading_agent.interfaces.facade.disciplines import (
    discipline_from_input,
    discipline_repository,
    evaluate_active_disciplines,
    get_discipline,
)
from ai_trading_agent.interfaces.facade.portfolio import (
    paper_position_from_input,
    paper_position_repository,
    watchlist_from_input,
    watchlist_repository,
)
from ai_trading_agent.interfaces.facade.research_workspace import (
    fund_research_payload,
    fund_research_report,
    get_strategy,
    instrument_from_query,
    latest_market_scan,
    latest_news,
    latest_quote,
    research,
    run_market_scan,
    strategy_from_input,
    strategy_repository,
    technical_study,
    today_candidates,
)
from ai_trading_agent.interfaces.model.http import (
    DEFAULT_NEWS_SOURCES,
    CandidateResponse,
    CandidateScreenResponse,
    ChatRequest,
    ChatResponse,
    DisciplineDecisionResponse,
    DisciplineInput,
    DisciplineResponse,
    FactorResponse,
    FundResearchResponse,
    MarketScanResponse,
    NewsItemResponse,
    PaperPositionInput,
    PaperPositionResponse,
    PaperPositionValuationResponse,
    QuoteQuery,
    QuoteResponse,
    ResearchRequest,
    ResearchResponse,
    StrategyInput,
    StrategyResponse,
    TechnicalRequest,
    TechnicalResponse,
    WatchlistInput,
    WatchlistResponse,
)


def create_app(*, cors_origins: tuple[str, ...] = ()) -> FastAPI:
    @asynccontextmanager
    async def lifespan(application: FastAPI):  # type: ignore[no-untyped-def]
        load_runtime_environment()
        yield

    app = FastAPI(title="My AI Trading Agent API", version="0.3.0", lifespan=lifespan)
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

    @app.post(
        "/api/v1/market/scans/{market}",
        response_model=MarketScanResponse,
        tags=["market"],
    )
    async def scan_market(market: Market) -> MarketScanResponse:
        try:
            return MarketScanResponse.from_domain(await run_market_scan(app, market))
        except Exception as error:
            raise HTTPException(status_code=503, detail=f"全市场扫描不可用：{error}") from error

    @app.get(
        "/api/v1/market/scans/{market}/latest",
        response_model=MarketScanResponse,
        tags=["market"],
    )
    async def get_latest_scan(market: Market) -> MarketScanResponse:
        try:
            run = await latest_market_scan(app, market)
            if run is None:
                raise HTTPException(status_code=404, detail="尚无该市场扫描记录")
            return MarketScanResponse.from_domain(run)
        except HTTPException:
            raise
        except Exception as error:
            raise HTTPException(status_code=503, detail=f"扫描记录不可用：{error}") from error

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

    @app.post("/api/v1/funds/research", response_model=FundResearchResponse, tags=["funds"])
    async def analyze_fund_research(query: QuoteQuery) -> FundResearchResponse:
        try:
            report = await fund_research_report(instrument_from_query(query))
            return FundResearchResponse(
                symbol=report.instrument.symbol,
                market=report.instrument.market,
                fund=fund_research_payload(report),
            )
        except Exception as error:
            raise HTTPException(status_code=503, detail=f"基金/ETF 研究不可用：{error}") from error

    @app.get("/api/v1/watchlist", response_model=list[WatchlistResponse], tags=["portfolio"])
    async def list_watchlist() -> list[WatchlistResponse]:
        return [
            WatchlistResponse.from_domain(item)
            for item in await ListWatchlistHandler(watchlist_repository(app)).handle()
        ]

    @app.post("/api/v1/watchlist", response_model=WatchlistResponse, tags=["portfolio"])
    async def save_watchlist(payload: WatchlistInput) -> WatchlistResponse:
        saved = await SaveWatchlistHandler(watchlist_repository(app)).handle(
            watchlist_from_input(payload, uuid4())
        )
        return WatchlistResponse.from_domain(saved)

    @app.delete("/api/v1/watchlist/{item_id}", status_code=204, tags=["portfolio"])
    async def delete_watchlist(item_id: UUID) -> None:
        if not await watchlist_repository(app).delete(str(item_id)):
            raise HTTPException(status_code=404, detail="watchlist item not found")

    @app.get(
        "/api/v1/paper-positions", response_model=list[PaperPositionResponse], tags=["portfolio"]
    )
    async def list_paper_positions() -> list[PaperPositionResponse]:
        return [
            PaperPositionResponse.from_domain(item)
            for item in await ListPaperPositionsHandler(paper_position_repository(app)).handle()
        ]

    @app.post("/api/v1/paper-positions", response_model=PaperPositionResponse, tags=["portfolio"])
    async def save_paper_position(payload: PaperPositionInput) -> PaperPositionResponse:
        saved = await SavePaperPositionHandler(paper_position_repository(app)).handle(
            paper_position_from_input(payload, uuid4())
        )
        return PaperPositionResponse.from_domain(saved)

    @app.get(
        "/api/v1/paper-positions/valuations",
        response_model=list[PaperPositionValuationResponse],
        tags=["portfolio"],
    )
    async def value_paper_positions() -> list[PaperPositionValuationResponse]:
        positions = await ListPaperPositionsHandler(paper_position_repository(app)).handle()
        values = []
        for position in positions:
            values.append(
                PaperPositionValuationResponse.from_domain(
                    value_paper_position(position, await latest_quote(position.instrument))
                )
            )
        return values

    @app.delete("/api/v1/paper-positions/{position_id}", status_code=204, tags=["portfolio"])
    async def delete_paper_position(position_id: UUID) -> None:
        if not await paper_position_repository(app).delete(str(position_id)):
            raise HTTPException(status_code=404, detail="paper position not found")

    @app.post("/api/v1/technical/study", response_model=TechnicalResponse, tags=["technical"])
    async def analyze_technical_study(query: TechnicalRequest) -> TechnicalResponse:
        try:
            return await technical_study(query)
        except Exception as error:
            raise HTTPException(status_code=503, detail=f"技术研究不可用：{error}") from error

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
        discipline_decisions: list[DisciplineDecisionResponse] = []
        if request.symbol and request.market:
            query = QuoteQuery(
                symbol=request.symbol,
                market=request.market,
                instrument_type=request.instrument_type,
            )
            try:
                quote = await latest_quote(instrument_from_query(query))
                context.append(
                    f"Quote: {quote.instrument.symbol} {quote.last_price} "
                    f"{quote.instrument.currency}; "
                    f"observed_at={quote.observed_at.isoformat()}; source={quote.source}."
                )
                statuses.append("已获取行情")
                try:
                    decisions = await evaluate_active_disciplines(
                        app,
                        quote.instrument,
                        quote,
                    )
                    discipline_decisions = [
                        DisciplineDecisionResponse.from_domain(decision) for decision in decisions
                    ]
                    if discipline_decisions:
                        context.append(
                            "Deterministic personal-discipline status "
                            "(binding rule-engine output; explain only, do not change):\n"
                            + "\n".join(
                                f"- {item.discipline_name}: {item.label}; {item.rationale}"
                                for item in discipline_decisions
                            )
                        )
                        statuses.append(
                            "已按个人纪律计算："
                            + "、".join(item.label for item in discipline_decisions)
                        )
                    else:
                        statuses.append("未找到此标的的启用个人纪律")
                except Exception as error:
                    statuses.append(f"个人纪律不可用：{error}")
            except Exception as error:
                statuses.append(f"行情不可用：{error}")
            report = await research(
                ResearchRequest(
                    symbol=request.symbol,
                    market=request.market,
                    instrument_type=request.instrument_type,
                    news_sources=request.news_sources,
                )
            )
            context.append(f"Research: {report.model_dump_json()}")
            statuses.append("已汇总研究分析")
            try:
                study = await technical_study(
                    TechnicalRequest(
                        symbol=request.symbol,
                        market=request.market,
                        instrument_type=request.instrument_type,
                    )
                )
                context.append(
                    f"Technical study (rule-based, not a trading signal): {study.model_dump_json()}"
                )
                statuses.append("已汇总 K 线、指标与成交量分布")
            except Exception as error:
                statuses.append(f"技术研究不可用：{error}")
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
            discipline_decisions=discipline_decisions,
            disclaimer="研究结果仅供信息与研究参考，不构成投资或交易指令。",
        )

    return app


app = create_app()
