"""FastAPI delivery routes for the research-agent interface."""

from __future__ import annotations

import asyncio
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
from ai_trading_agent.domain.enums.candidates import CandidateRanking
from ai_trading_agent.domain.enums.market import Market
from ai_trading_agent.infrastructure.config.providers import (
    AiSimulationSchedulerSettings,
    ClosingPlanSchedulerSettings,
    WatchlistAnalysisSettings,
)
from ai_trading_agent.interfaces.adapter.environment import load_runtime_environment
from ai_trading_agent.interfaces.facade.ai_simulation import (
    AiSimulationRunRequest,
    ai_simulation_overview,
    ai_simulation_runs,
    run_ai_simulation,
    run_scheduled_ai_simulations,
    update_ai_simulation_settings,
)
from ai_trading_agent.interfaces.facade.closing_plan import (
    closing_plan,
    refresh_closing_plan,
    refresh_closing_window_analyses,
)
from ai_trading_agent.interfaces.facade.disciplines import (
    discipline_from_input,
    discipline_repository,
    get_discipline,
)
from ai_trading_agent.interfaces.facade.instruments import resolve_instrument_identity
from ai_trading_agent.interfaces.facade.market_assistant import answer_market_question
from ai_trading_agent.interfaces.facade.market_brief import post_market_brief
from ai_trading_agent.interfaces.facade.portfolio import (
    get_watchlist_item,
    paper_portfolio_overview,
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
    watchlist_financial_detail,
)
from ai_trading_agent.interfaces.facade.watchlist_analysis import (
    latest_watchlist_analyses,
    latest_watchlist_analysis,
    refresh_all_watchlist_analyses,
    refresh_watchlist_analysis,
)
from ai_trading_agent.interfaces.model.http import (
    DEFAULT_NEWS_SOURCES,
    AiSimulationOverviewResponse,
    AiSimulationRunInput,
    AiSimulationRunResponse,
    CandidateResponse,
    CandidateScreenResponse,
    ClosingPlanResponse,
    DisciplineInput,
    DisciplineResponse,
    FactorResponse,
    FundResearchResponse,
    InstrumentIdentityResponse,
    MarketQuestionRequest,
    MarketQuestionResponse,
    MarketScanResponse,
    NewsItemResponse,
    PaperPortfolioOverviewResponse,
    PaperPositionInput,
    PaperPositionResponse,
    PaperPositionValuationResponse,
    PostMarketBriefResponse,
    QuoteQuery,
    QuoteResponse,
    ResearchRequest,
    ResearchResponse,
    StrategyInput,
    StrategyResponse,
    TechnicalRequest,
    TechnicalResponse,
    WatchlistAnalysisResponse,
    WatchlistFinancialDetailResponse,
    WatchlistInput,
    WatchlistResponse,
)
from ai_trading_agent.interfaces.task.market_scans import RecurringTaskScheduler


async def _display_name(instrument) -> str | None:  # type: ignore[no-untyped-def]
    """Identity lookup must never make an existing private list unavailable."""
    try:
        identity = await resolve_instrument_identity(instrument)
        return None if identity is None else identity.display_name
    except Exception:
        return None


def create_app(
    *,
    cors_origins: tuple[str, ...] = (),
    enable_scheduled_tasks: bool = False,
) -> FastAPI:
    @asynccontextmanager
    async def lifespan(application: FastAPI):  # type: ignore[no-untyped-def]
        load_runtime_environment()
        schedulers: list[RecurringTaskScheduler] = []
        watchlist_settings = WatchlistAnalysisSettings.from_environment()
        if enable_scheduled_tasks and watchlist_settings.scheduler_enabled:
            scheduler = RecurringTaskScheduler(
                lambda: refresh_all_watchlist_analyses(application),
                watchlist_settings.interval_seconds,
            )
            scheduler.start()
            application.state.watchlist_analysis_scheduler = scheduler
            schedulers.append(scheduler)
        closing_plan_settings = ClosingPlanSchedulerSettings.from_environment()
        if enable_scheduled_tasks and closing_plan_settings.scheduler_enabled:
            scheduler = RecurringTaskScheduler(
                lambda: refresh_closing_window_analyses(application),
                closing_plan_settings.interval_seconds,
                run_immediately=True,
                align_to_interval_boundary=True,
            )
            scheduler.start()
            application.state.closing_plan_scheduler = scheduler
            schedulers.append(scheduler)
        ai_settings = AiSimulationSchedulerSettings.from_environment()
        if enable_scheduled_tasks and ai_settings.scheduler_enabled:
            scheduler = RecurringTaskScheduler(
                lambda: run_scheduled_ai_simulations(
                    application,
                    trading_days_only=ai_settings.trading_days_only,
                    market_hours_only=ai_settings.market_hours_only,
                    run_timeout_seconds=ai_settings.run_timeout_seconds,
                ),
                ai_settings.interval_seconds,
                run_immediately=False,
                align_to_interval_boundary=True,
            )
            scheduler.start()
            application.state.ai_simulation_scheduler = scheduler
            schedulers.append(scheduler)
        try:
            yield
        finally:
            for scheduler in schedulers:
                await scheduler.stop()

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

    @app.post(
        "/api/v1/instruments/resolve",
        response_model=InstrumentIdentityResponse,
        tags=["instruments"],
    )
    async def resolve_instrument(query: QuoteQuery) -> InstrumentIdentityResponse:
        try:
            identity = await resolve_instrument_identity(instrument_from_query(query))
            return InstrumentIdentityResponse.from_resolution(
                query,
                None if identity is None else identity.display_name,
                None if identity is None else identity.source,
            )
        except Exception as error:
            raise HTTPException(status_code=503, detail=f"标的名称识别暂不可用：{error}") from error

    @app.get(
        "/api/v1/market/post-market-brief",
        response_model=PostMarketBriefResponse,
        tags=["market"],
    )
    async def get_post_market_brief(refresh: bool = False) -> PostMarketBriefResponse:
        try:
            return PostMarketBriefResponse.from_domain(await post_market_brief(refresh=refresh))
        except Exception as error:
            raise HTTPException(status_code=503, detail=f"盘后快报暂不可用：{error}") from error

    @app.post(
        "/api/v1/assistant/market-question",
        response_model=MarketQuestionResponse,
        tags=["assistant"],
    )
    async def ask_market_question(payload: MarketQuestionRequest) -> MarketQuestionResponse:
        try:
            return MarketQuestionResponse.from_domain(
                await answer_market_question(payload.question)
            )
        except ValueError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
        except Exception as error:
            raise HTTPException(status_code=503, detail=f"市场问答暂不可用：{error}") from error

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
            sources = tuple(
                dict.fromkeys(item.observation.source for item in screen.candidates)
            )
            return CandidateScreenResponse(
                market=market,
                ranking=ranking,
                candidates=[CandidateResponse.from_domain(item) for item in screen.candidates],
                universe_size=screen.universe_size,
                refreshed_at=refreshed_at.isoformat(),
                source=" + ".join(sources),
                coverage=(
                    "已筛选预设高流动性股票研究样本；腾讯失败时，"
                    "A 股自动降级至同花顺/Futu，港美股自动降级至 Futu。"
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
        items = await ListWatchlistHandler(watchlist_repository(app)).handle()
        names = await asyncio.gather(*(_display_name(item.instrument) for item in items))
        return [
            WatchlistResponse.from_domain(item, display_name=name)
            for item, name in zip(items, names, strict=True)
        ]

    @app.post("/api/v1/watchlist", response_model=WatchlistResponse, tags=["portfolio"])
    async def save_watchlist(payload: WatchlistInput) -> WatchlistResponse:
        instrument = instrument_from_query(payload)
        display_name = await _display_name(instrument)
        resolved_payload = payload.model_copy(
            update={"label": payload.label.strip() or display_name or ""}
        )
        saved = await SaveWatchlistHandler(watchlist_repository(app)).handle(
            watchlist_from_input(resolved_payload, uuid4())
        )
        return WatchlistResponse.from_domain(saved, display_name=display_name)

    @app.delete("/api/v1/watchlist/{item_id}", status_code=204, tags=["portfolio"])
    async def delete_watchlist(item_id: UUID) -> None:
        if not await watchlist_repository(app).delete(str(item_id)):
            raise HTTPException(status_code=404, detail="watchlist item not found")

    @app.get(
        "/api/v1/watchlist/analyses",
        response_model=list[WatchlistAnalysisResponse],
        tags=["watchlist-analysis"],
    )
    async def list_latest_watchlist_analyses() -> list[WatchlistAnalysisResponse]:
        try:
            return [
                WatchlistAnalysisResponse.from_domain(item)
                for item in await latest_watchlist_analyses(app)
            ]
        except Exception as error:
            raise HTTPException(status_code=503, detail=f"自选分析不可用：{error}") from error

    @app.get(
        "/api/v1/closing-plan",
        response_model=ClosingPlanResponse,
        tags=["closing-plan"],
    )
    async def get_closing_plan() -> ClosingPlanResponse:
        try:
            return ClosingPlanResponse.from_domain(await closing_plan(app))
        except Exception as error:
            raise HTTPException(status_code=503, detail=f"尾盘计划不可用：{error}") from error

    @app.post(
        "/api/v1/closing-plan/refresh",
        response_model=ClosingPlanResponse,
        tags=["closing-plan"],
    )
    async def refresh_current_closing_plan() -> ClosingPlanResponse:
        try:
            return ClosingPlanResponse.from_domain(await refresh_closing_plan(app))
        except Exception as error:
            raise HTTPException(status_code=503, detail=f"尾盘评估刷新失败：{error}") from error

    @app.get(
        "/api/v1/watchlist/{item_id}/analysis",
        response_model=WatchlistAnalysisResponse,
        tags=["watchlist-analysis"],
    )
    async def get_latest_watchlist_analysis(item_id: UUID) -> WatchlistAnalysisResponse:
        try:
            analysis = await latest_watchlist_analysis(app, str(item_id))
            if analysis is None:
                raise HTTPException(status_code=404, detail="尚无此自选标的的分析结果")
            return WatchlistAnalysisResponse.from_domain(analysis)
        except HTTPException:
            raise
        except Exception as error:
            raise HTTPException(status_code=503, detail=f"自选分析不可用：{error}") from error

    @app.post(
        "/api/v1/watchlist/{item_id}/analysis/refresh",
        response_model=WatchlistAnalysisResponse,
        tags=["watchlist-analysis"],
    )
    async def refresh_one_watchlist_analysis(item_id: UUID) -> WatchlistAnalysisResponse:
        try:
            item = await get_watchlist_item(app, item_id)
            if item is None:
                raise HTTPException(status_code=404, detail="watchlist item not found")
            analysis = await refresh_watchlist_analysis(app, item, force=True)
            return WatchlistAnalysisResponse.from_domain(analysis)
        except HTTPException:
            raise
        except Exception as error:
            raise HTTPException(status_code=503, detail=f"自选分析刷新失败：{error}") from error

    @app.get(
        "/api/v1/watchlist/{item_id}/deep-dive",
        response_model=WatchlistFinancialDetailResponse,
        tags=["watchlist-analysis"],
    )
    async def get_watchlist_deep_dive(item_id: UUID) -> WatchlistFinancialDetailResponse:
        try:
            item = await get_watchlist_item(app, item_id)
            if item is None:
                raise HTTPException(status_code=404, detail="watchlist item not found")
            detail = await watchlist_financial_detail(item.instrument)
            return WatchlistFinancialDetailResponse.from_domain(detail)
        except HTTPException:
            raise
        except Exception as error:
            raise HTTPException(status_code=503, detail=f"自选深度数据不可用：{error}") from error

    @app.get(
        "/api/v1/paper-positions", response_model=list[PaperPositionResponse], tags=["portfolio"]
    )
    async def list_paper_positions() -> list[PaperPositionResponse]:
        positions = await ListPaperPositionsHandler(paper_position_repository(app)).handle()
        names = await asyncio.gather(*(_display_name(item.instrument) for item in positions))
        return [
            PaperPositionResponse.from_domain(item, display_name=name)
            for item, name in zip(positions, names, strict=True)
        ]

    @app.post("/api/v1/paper-positions", response_model=PaperPositionResponse, tags=["portfolio"])
    async def save_paper_position(payload: PaperPositionInput) -> PaperPositionResponse:
        saved = await SavePaperPositionHandler(paper_position_repository(app)).handle(
            paper_position_from_input(payload, uuid4())
        )
        return PaperPositionResponse.from_domain(
            saved, display_name=await _display_name(saved.instrument)
        )

    @app.get(
        "/api/v1/paper-positions/valuations",
        response_model=list[PaperPositionValuationResponse],
        tags=["portfolio"],
    )
    async def value_paper_positions() -> list[PaperPositionValuationResponse]:
        positions = await ListPaperPositionsHandler(paper_position_repository(app)).handle()
        overview = await paper_portfolio_overview(positions)
        return [PaperPositionValuationResponse.from_domain(item) for item in overview.valuations]

    @app.get(
        "/api/v1/paper-positions/overview",
        response_model=PaperPortfolioOverviewResponse,
        tags=["portfolio"],
    )
    async def get_paper_portfolio_overview() -> PaperPortfolioOverviewResponse:
        try:
            positions = await ListPaperPositionsHandler(paper_position_repository(app)).handle()
            return PaperPortfolioOverviewResponse.from_domain(
                await paper_portfolio_overview(positions)
            )
        except Exception as error:
            raise HTTPException(status_code=503, detail=f"模拟组合估值不可用：{error}") from error

    @app.get(
        "/api/v1/ai-simulation/overview",
        response_model=AiSimulationOverviewResponse,
        tags=["ai-simulation"],
    )
    async def get_ai_simulation_overview(market: Market) -> AiSimulationOverviewResponse:
        try:
            if market is Market.FUND:
                raise ValueError("AI 模拟选股当前仅支持 A 股、港股和美股股票样本")
            return AiSimulationOverviewResponse.from_domain(
                await ai_simulation_overview(app, market)
            )
        except LookupError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        except ValueError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
        except Exception as error:
            raise HTTPException(
                status_code=503, detail=f"AI 模拟组合估值不可用：{error}"
            ) from error

    @app.get(
        "/api/v1/ai-simulation/runs",
        response_model=list[AiSimulationRunResponse],
        tags=["ai-simulation"],
    )
    async def get_ai_simulation_runs(
        market: Market, limit: int = 14
    ) -> list[AiSimulationRunResponse]:
        if market is Market.FUND:
            raise HTTPException(status_code=422, detail="AI 模拟选股当前仅支持股票市场")
        if not 1 <= limit <= 60:
            raise HTTPException(status_code=422, detail="limit must be between 1 and 60")
        try:
            return [
                AiSimulationRunResponse.from_domain(item)
                for item in await ai_simulation_runs(app, market, limit)
            ]
        except Exception as error:
            raise HTTPException(status_code=503, detail=f"AI 模拟历史读取失败：{error}") from error

    @app.post(
        "/api/v1/ai-simulation/run",
        response_model=AiSimulationOverviewResponse,
        tags=["ai-simulation"],
    )
    async def run_ai_simulation_cycle(
        payload: AiSimulationRunInput,
    ) -> AiSimulationOverviewResponse:
        try:
            if payload.market is Market.FUND:
                raise ValueError("AI 模拟选股当前仅支持 A 股、港股和美股股票样本")
            return AiSimulationOverviewResponse.from_domain(
                await run_ai_simulation(
                    app,
                    AiSimulationRunRequest(
                        market=payload.market,
                        initial_capital=payload.initial_capital,
                        max_positions=payload.max_positions,
                        strategy_ids=tuple(payload.strategy_ids),
                    ),
                )
            )
        except ValueError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
        except Exception as error:
            raise HTTPException(status_code=503, detail=f"AI 模拟选股暂不可用：{error}") from error

    @app.put(
        "/api/v1/ai-simulation/settings",
        response_model=AiSimulationOverviewResponse,
        tags=["ai-simulation"],
    )
    async def save_ai_simulation_settings(
        payload: AiSimulationRunInput,
    ) -> AiSimulationOverviewResponse:
        try:
            if payload.market is Market.FUND:
                raise ValueError("AI 模拟选股当前仅支持 A 股、港股和美股股票样本")
            return AiSimulationOverviewResponse.from_domain(
                await update_ai_simulation_settings(
                    app,
                    AiSimulationRunRequest(
                        market=payload.market,
                        initial_capital=payload.initial_capital,
                        max_positions=payload.max_positions,
                        strategy_ids=tuple(payload.strategy_ids),
                    ),
                )
            )
        except LookupError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        except ValueError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
        except Exception as error:
            raise HTTPException(status_code=503, detail=f"AI 模拟账户更新失败：{error}") from error

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

    return app


app = create_app(enable_scheduled_tasks=True)
