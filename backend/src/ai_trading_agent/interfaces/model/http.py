"""HTTP request and response contracts; no infrastructure calls occur here."""

from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from ai_trading_agent.domain.ability.factors import FactorMetadata
from ai_trading_agent.domain.aggregate.ai_simulation import AiSimulationOverview
from ai_trading_agent.domain.aggregate.candidate import RankedCandidate
from ai_trading_agent.domain.aggregate.discipline import TradingDiscipline
from ai_trading_agent.domain.aggregate.discipline_decision import DisciplineDecision
from ai_trading_agent.domain.aggregate.market import Quote
from ai_trading_agent.domain.aggregate.market_assistant import MarketAssistantAnswer
from ai_trading_agent.domain.aggregate.market_brief import PostMarketBrief
from ai_trading_agent.domain.aggregate.market_scan import MarketScanRun
from ai_trading_agent.domain.aggregate.strategy import StrategyProfile
from ai_trading_agent.domain.aggregate.watchlist import (
    PaperPortfolioOverview,
    PaperPortfolioSummary,
    PaperPosition,
    PaperPositionValuation,
    WatchlistItem,
)
from ai_trading_agent.domain.aggregate.watchlist_analysis import WatchlistAnalysisSnapshot
from ai_trading_agent.domain.aggregate.watchlist_detail import WatchlistFinancialDetail
from ai_trading_agent.domain.enums.candidates import CandidateRanking
from ai_trading_agent.domain.enums.market import InstrumentType, Market
from ai_trading_agent.domain.enums.research import (
    DisciplineDecisionStatus,
    DisciplineStatus,
    WatchlistAnalysisStatus,
)
from ai_trading_agent.domain.enums.technical import BarTimeframe

DEFAULT_NEWS_SOURCES = ("eastmoney", "sina")


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


class InstrumentIdentityResponse(BaseModel):
    symbol: str
    market: Market
    instrument_type: InstrumentType
    display_name: str | None
    source: str | None

    @classmethod
    def from_resolution(
        cls,
        query: QuoteQuery,
        display_name: str | None,
        source: str | None,
    ) -> InstrumentIdentityResponse:
        return cls(
            symbol=query.symbol,
            market=query.market,
            instrument_type=query.instrument_type,
            display_name=display_name,
            source=source,
        )


class MarketIndexResponse(BaseModel):
    symbol: str
    name: str
    last_price: Decimal
    price_change: Decimal | None
    change_percent: Decimal | None


class SectorRotationResponse(BaseModel):
    symbol: str
    name: str
    last_price: Decimal
    change_percent: Decimal


class PostMarketBriefResponse(BaseModel):
    observed_at: str
    source: str
    indices: list[MarketIndexResponse]
    leading_sectors: list[SectorRotationResponse]
    lagging_sectors: list[SectorRotationResponse]
    coverage: str
    disclaimer: str

    @classmethod
    def from_domain(cls, brief: PostMarketBrief) -> PostMarketBriefResponse:
        return cls(
            observed_at=brief.observed_at.isoformat(),
            source=brief.source,
            indices=[
                MarketIndexResponse(
                    symbol=item.symbol,
                    name=item.name,
                    last_price=item.last_price,
                    price_change=item.price_change,
                    change_percent=item.change_percent,
                )
                for item in brief.indices
            ],
            leading_sectors=[
                SectorRotationResponse(
                    symbol=item.symbol,
                    name=item.name,
                    last_price=item.last_price,
                    change_percent=item.change_percent,
                )
                for item in brief.leading_sectors
            ],
            lagging_sectors=[
                SectorRotationResponse(
                    symbol=item.symbol,
                    name=item.name,
                    last_price=item.last_price,
                    change_percent=item.change_percent,
                )
                for item in brief.lagging_sectors
            ],
            coverage=(
                "同花顺指数快照：上证、深成、创业板和沪深 300；"
                "行业板块按公开的同花顺行业指数当日涨跌幅排序。"
            ),
            disclaimer=(
                "板块轮动仅按指数涨跌幅呈现，并非主力资金流、持仓或交易信号；"
                "盘中访问时显示的是最新快照，并非已收盘结论。"
            ),
        )


class MarketQuestionRequest(BaseModel):
    question: str = Field(min_length=2, max_length=500)


class MarketQuestionCandidateResponse(BaseModel):
    symbol: str
    name: str
    asset_type: str
    exchange: str | None
    currency: str | None
    source: str


class MarketQuestionResponse(BaseModel):
    answer: str
    generated_at: str
    sources: list[str]
    notices: list[str]
    candidates: list[MarketQuestionCandidateResponse]

    @classmethod
    def from_domain(cls, answer: MarketAssistantAnswer) -> MarketQuestionResponse:
        return cls(
            answer=answer.answer,
            generated_at=answer.generated_at.isoformat(),
            sources=list(answer.sources),
            notices=list(answer.notices),
            candidates=[
                MarketQuestionCandidateResponse(
                    symbol=item.symbol,
                    name=item.name,
                    asset_type=item.asset_type,
                    exchange=item.exchange,
                    currency=item.currency,
                    source=item.source,
                )
                for item in answer.candidates
            ],
        )


class CandidateResponse(BaseModel):
    symbol: str
    name: str
    market: Market
    currency: str
    last_price: Decimal
    change_percent: Decimal | None
    score: Decimal
    reasons: list[str]
    observed_at: str
    source: str

    @classmethod
    def from_domain(cls, candidate: RankedCandidate) -> CandidateResponse:
        observation = candidate.observation
        return cls(
            symbol=observation.instrument.symbol,
            name=observation.name,
            market=observation.instrument.market,
            currency=observation.instrument.currency,
            last_price=observation.last_price,
            change_percent=observation.change_percent,
            score=candidate.score,
            reasons=list(candidate.reasons),
            observed_at=observation.observed_at.isoformat(),
            source=observation.source,
        )


class CandidateScreenResponse(BaseModel):
    market: Market
    ranking: CandidateRanking
    candidates: list[CandidateResponse]
    universe_size: int
    refreshed_at: str
    source: str
    coverage: str
    disclaimer: str


class MarketScanResponse(BaseModel):
    run_id: UUID
    market: Market
    source: str
    status: str
    started_at: str
    completed_at: str
    universe_size: int
    snapshot_count: int
    error_message: str | None

    @classmethod
    def from_domain(cls, run: MarketScanRun) -> MarketScanResponse:
        return cls(
            run_id=run.run_id,
            market=run.market,
            source=run.source,
            status=run.status,
            started_at=run.started_at.isoformat(),
            completed_at=run.completed_at.isoformat(),
            universe_size=run.universe_size,
            snapshot_count=run.snapshot_count,
            error_message=run.error_message,
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
    fund_research: dict[str, object] | None = None
    factor_analysis: dict[str, object] | None = None
    notices: list[str]


class IncomeStatementSummaryResponse(BaseModel):
    report_period: str
    announced_on: str
    currency: str
    operating_income: Decimal | None
    operating_profit: Decimal | None
    net_profit: Decimal | None
    basic_eps: Decimal | None


class BalanceSheetSummaryResponse(BaseModel):
    report_period: str
    currency: str
    total_assets: Decimal | None
    total_debt: Decimal | None
    total_equity: Decimal | None
    cash: Decimal | None
    accounts_receivable: Decimal | None
    debt_to_assets_percent: Decimal | None


class CashFlowSummaryResponse(BaseModel):
    report_period: str
    currency: str
    operating_cash_flow: Decimal | None
    investing_cash_flow: Decimal | None
    financing_cash_flow: Decimal | None
    net_cash_change: Decimal | None


class ValuationSummaryResponse(BaseModel):
    observed_at: str | None
    price_to_earnings_ttm: Decimal | None
    price_to_earnings_mrq: Decimal | None
    price_to_book_mrq: Decimal | None
    price_to_sales_ttm: Decimal | None
    price_to_cash_flow_ttm: Decimal | None


class TimeCatalystResponse(BaseModel):
    occurred_on: str
    title: str
    detail: str
    kind: str


class WatchlistFinancialDetailResponse(BaseModel):
    symbol: str
    market: Market
    instrument_type: InstrumentType
    observed_at: str
    source: str
    income_statement: IncomeStatementSummaryResponse | None
    balance_sheet: BalanceSheetSummaryResponse | None
    cash_flow: CashFlowSummaryResponse | None
    valuation: ValuationSummaryResponse | None
    time_catalysts: list[TimeCatalystResponse]
    notices: list[str]

    @classmethod
    def from_domain(cls, detail: WatchlistFinancialDetail) -> WatchlistFinancialDetailResponse:
        income = detail.income_statement
        balance = detail.balance_sheet
        cash_flow = detail.cash_flow
        valuation = detail.valuation
        return cls(
            symbol=detail.instrument.symbol,
            market=detail.instrument.market,
            instrument_type=detail.instrument.instrument_type,
            observed_at=detail.observed_at.isoformat(),
            source=detail.source,
            income_statement=(
                None
                if income is None
                else IncomeStatementSummaryResponse(
                    report_period=income.report_period.isoformat(),
                    announced_on=income.announced_on.isoformat(),
                    currency=income.currency,
                    operating_income=income.operating_income,
                    operating_profit=income.operating_profit,
                    net_profit=income.net_profit,
                    basic_eps=income.basic_eps,
                )
            ),
            balance_sheet=(
                None
                if balance is None
                else BalanceSheetSummaryResponse(
                    report_period=balance.report_period.isoformat(),
                    currency=balance.currency,
                    total_assets=balance.total_assets,
                    total_debt=balance.total_debt,
                    total_equity=balance.total_equity,
                    cash=balance.cash,
                    accounts_receivable=balance.accounts_receivable,
                    debt_to_assets_percent=balance.debt_to_assets_percent,
                )
            ),
            cash_flow=(
                None
                if cash_flow is None
                else CashFlowSummaryResponse(
                    report_period=cash_flow.report_period.isoformat(),
                    currency=cash_flow.currency,
                    operating_cash_flow=cash_flow.operating_cash_flow,
                    investing_cash_flow=cash_flow.investing_cash_flow,
                    financing_cash_flow=cash_flow.financing_cash_flow,
                    net_cash_change=cash_flow.net_cash_change,
                )
            ),
            valuation=(
                None
                if valuation is None
                else ValuationSummaryResponse(
                    observed_at=(
                        valuation.observed_at.isoformat()
                        if valuation.observed_at is not None
                        else None
                    ),
                    price_to_earnings_ttm=valuation.price_to_earnings_ttm,
                    price_to_earnings_mrq=valuation.price_to_earnings_mrq,
                    price_to_book_mrq=valuation.price_to_book_mrq,
                    price_to_sales_ttm=valuation.price_to_sales_ttm,
                    price_to_cash_flow_ttm=valuation.price_to_cash_flow_ttm,
                )
            ),
            time_catalysts=[
                TimeCatalystResponse(
                    occurred_on=item.occurred_on.isoformat(),
                    title=item.title,
                    detail=item.detail,
                    kind=item.kind,
                )
                for item in detail.time_catalysts
            ],
            notices=list(detail.notices),
        )


class FundResearchResponse(BaseModel):
    symbol: str
    market: Market
    fund: dict[str, object]


class WatchlistInput(QuoteQuery):
    label: str = Field(default="", max_length=160)
    notes: str = Field(default="", max_length=4_000)


class WatchlistResponse(WatchlistInput):
    item_id: UUID
    display_name: str | None = None

    @classmethod
    def from_domain(
        cls, item: WatchlistItem, *, display_name: str | None = None
    ) -> WatchlistResponse:
        return cls(
            item_id=item.item_id,
            symbol=item.instrument.symbol,
            market=item.instrument.market,
            instrument_type=item.instrument.instrument_type,
            label=item.label,
            notes=item.notes,
            display_name=display_name or item.label or None,
        )


class WatchlistAnalysisTagResponse(BaseModel):
    category: str
    label: str
    tone: str


class WatchlistAnalysisResponse(BaseModel):
    analysis_id: UUID
    watchlist_item_id: UUID
    symbol: str
    market: Market
    instrument_type: InstrumentType
    observed_at: str
    status: WatchlistAnalysisStatus
    tags: list[WatchlistAnalysisTagResponse]
    ai_summary: str | None
    notices: list[str]

    @classmethod
    def from_domain(cls, analysis: WatchlistAnalysisSnapshot) -> WatchlistAnalysisResponse:
        return cls(
            analysis_id=analysis.analysis_id,
            watchlist_item_id=analysis.watchlist_item_id,
            symbol=analysis.instrument.symbol,
            market=analysis.instrument.market,
            instrument_type=analysis.instrument.instrument_type,
            observed_at=analysis.observed_at.isoformat(),
            status=analysis.status,
            tags=[
                WatchlistAnalysisTagResponse(
                    category=tag.category,
                    label=tag.label,
                    tone=tag.tone,
                )
                for tag in analysis.tags
            ],
            ai_summary=analysis.ai_summary,
            notices=list(analysis.notices),
        )


class PaperPositionInput(QuoteQuery):
    quantity: Decimal = Field(gt=0)
    average_cost: Decimal = Field(gt=0)
    notes: str = Field(default="", max_length=4_000)


class PaperPositionResponse(PaperPositionInput):
    position_id: UUID
    display_name: str | None = None
    cost_amount: Decimal

    @classmethod
    def from_domain(
        cls, position: PaperPosition, *, display_name: str | None = None
    ) -> PaperPositionResponse:
        return cls(
            position_id=position.position_id,
            symbol=position.instrument.symbol,
            market=position.instrument.market,
            instrument_type=position.instrument.instrument_type,
            quantity=position.quantity,
            average_cost=position.average_cost,
            cost_amount=position.cost_basis,
            notes=position.notes,
            display_name=display_name,
        )


class PaperPositionValuationResponse(PaperPositionResponse):
    last_price: Decimal
    currency: str
    observed_at: str
    source: str
    market_value: Decimal
    unrealized_pnl: Decimal
    unrealized_pnl_percent: Decimal
    daily_pnl: Decimal | None
    daily_pnl_percent: Decimal | None
    month_to_date_pnl: Decimal | None
    month_to_date_pnl_percent: Decimal | None
    month_reference_date: str | None

    @classmethod
    def from_domain(cls, valuation: PaperPositionValuation) -> PaperPositionValuationResponse:
        base = PaperPositionResponse.from_domain(valuation.position).model_dump()
        return cls(
            **base,
            last_price=valuation.quote.last_price,
            currency=valuation.quote.instrument.currency,
            observed_at=valuation.quote.observed_at.isoformat(),
            source=valuation.quote.source,
            market_value=valuation.market_value,
            unrealized_pnl=valuation.unrealized_pnl,
            unrealized_pnl_percent=valuation.unrealized_pnl_percent,
            daily_pnl=valuation.daily_pnl,
            daily_pnl_percent=valuation.daily_pnl_percent,
            month_to_date_pnl=valuation.month_to_date_pnl,
            month_to_date_pnl_percent=valuation.month_to_date_pnl_percent,
            month_reference_date=(
                valuation.month_reference_date.isoformat()
                if valuation.month_reference_date is not None
                else None
            ),
        )


class PaperPortfolioCurrencySummaryResponse(BaseModel):
    currency: str
    position_count: int
    initial_principal: Decimal
    total_market_value: Decimal
    cumulative_pnl: Decimal
    cumulative_return_percent: Decimal
    daily_pnl: Decimal | None
    daily_return_percent: Decimal | None
    month_to_date_pnl: Decimal | None
    month_to_date_return_percent: Decimal | None
    daily_coverage_count: int
    month_coverage_count: int


class PaperPortfolioOverviewResponse(BaseModel):
    observed_at: str
    valued_position_count: int
    total_position_count: int
    currencies: list[PaperPortfolioCurrencySummaryResponse]
    valuations: list[PaperPositionValuationResponse]
    notices: list[str]

    @classmethod
    def from_domain(cls, overview: PaperPortfolioOverview) -> PaperPortfolioOverviewResponse:
        summary: PaperPortfolioSummary = overview.summary
        return cls(
            observed_at=summary.observed_at.isoformat(),
            valued_position_count=summary.valued_position_count,
            total_position_count=summary.total_position_count,
            currencies=[
                PaperPortfolioCurrencySummaryResponse(
                    currency=item.currency,
                    position_count=item.position_count,
                    initial_principal=item.initial_principal,
                    total_market_value=item.total_market_value,
                    cumulative_pnl=item.cumulative_pnl,
                    cumulative_return_percent=item.cumulative_return_percent,
                    daily_pnl=item.daily_pnl,
                    daily_return_percent=item.daily_return_percent,
                    month_to_date_pnl=item.month_to_date_pnl,
                    month_to_date_return_percent=item.month_to_date_return_percent,
                    daily_coverage_count=item.daily_coverage_count,
                    month_coverage_count=item.month_coverage_count,
                )
                for item in summary.currencies
            ],
            valuations=[
                PaperPositionValuationResponse.from_domain(item) for item in overview.valuations
            ],
            notices=list(overview.notices),
        )


class AiSimulationRunInput(BaseModel):
    market: Market
    initial_capital: Decimal = Field(gt=0)
    max_positions: int = Field(default=3, ge=1, le=10)
    strategy_id: UUID | None = None


class AiSimulationPositionResponse(BaseModel):
    position_id: UUID
    symbol: str
    display_name: str | None
    market: Market
    instrument_type: InstrumentType
    quantity: Decimal
    average_cost: Decimal
    cost_amount: Decimal
    candidate_score: Decimal
    factor_context: list[str]
    rationale: list[str]
    opened_at: str
    last_price: Decimal | None
    market_value: Decimal | None
    unrealized_pnl: Decimal | None
    unrealized_pnl_percent: Decimal | None
    daily_pnl: Decimal | None
    month_to_date_pnl: Decimal | None
    source: str | None


class AiSimulationDecisionResponse(BaseModel):
    symbol: str
    display_name: str | None
    score: Decimal
    decision: str
    supportive_factor_count: int
    adverse_factor_count: int
    available_factor_ids: list[str]
    unavailable_factor_ids: list[str]
    blockers: list[str]


class AiSimulationRunResponse(BaseModel):
    run_id: UUID
    portfolio_id: UUID
    market: Market
    trigger: str
    status: str
    started_at: str
    completed_at: str
    position_count: int
    total_equity: Decimal | None
    decision_reports: list[AiSimulationDecisionResponse]
    notices: list[str]
    error_message: str | None

    @classmethod
    def from_domain(cls, run) -> AiSimulationRunResponse:  # type: ignore[no-untyped-def]
        return cls(
            run_id=run.run_id,
            portfolio_id=run.portfolio_id,
            market=run.market,
            trigger=run.trigger,
            status=run.status,
            started_at=run.started_at.isoformat(),
            completed_at=run.completed_at.isoformat(),
            position_count=run.position_count,
            total_equity=run.total_equity,
            decision_reports=[
                AiSimulationDecisionResponse(
                    symbol=item.symbol,
                    display_name=item.display_name,
                    score=item.score,
                    decision=item.decision,
                    supportive_factor_count=item.supportive_factor_count,
                    adverse_factor_count=item.adverse_factor_count,
                    available_factor_ids=list(item.available_factor_ids),
                    unavailable_factor_ids=list(item.unavailable_factor_ids),
                    blockers=list(item.blockers),
                )
                for item in run.decision_reports
            ],
            notices=list(run.notices),
            error_message=run.error_message,
        )


class AiSimulationOverviewResponse(BaseModel):
    portfolio_id: UUID
    market: Market
    currency: str
    initial_capital: Decimal
    cash_balance: Decimal
    invested_cost: Decimal
    market_value: Decimal
    total_equity: Decimal
    cumulative_pnl: Decimal
    daily_pnl: Decimal | None
    month_to_date_pnl: Decimal | None
    max_positions: int
    strategy_id: UUID | None
    observed_at: str
    positions: list[AiSimulationPositionResponse]
    notices: list[str]
    decision_reports: list[AiSimulationDecisionResponse]

    @classmethod
    def from_domain(cls, overview: AiSimulationOverview) -> AiSimulationOverviewResponse:
        portfolio = overview.portfolio
        return cls(
            portfolio_id=portfolio.portfolio_id,
            market=Market(portfolio.market),
            currency=portfolio.currency,
            initial_capital=portfolio.initial_capital,
            cash_balance=portfolio.cash_balance,
            invested_cost=overview.invested_cost,
            market_value=overview.market_value,
            total_equity=overview.total_equity,
            cumulative_pnl=overview.cumulative_pnl,
            daily_pnl=overview.daily_pnl,
            month_to_date_pnl=overview.month_to_date_pnl,
            max_positions=portfolio.max_positions,
            strategy_id=portfolio.strategy_id,
            observed_at=overview.observed_at.isoformat(),
            positions=[
                AiSimulationPositionResponse(
                    position_id=item.position.position_id,
                    symbol=item.position.instrument.symbol,
                    display_name=item.display_name,
                    market=item.position.instrument.market,
                    instrument_type=item.position.instrument.instrument_type,
                    quantity=item.position.quantity,
                    average_cost=item.position.average_cost,
                    cost_amount=item.position.cost_amount,
                    candidate_score=item.position.candidate_score,
                    factor_context=list(item.position.factor_context),
                    rationale=list(item.position.rationale),
                    opened_at=item.position.opened_at.isoformat(),
                    last_price=item.last_price,
                    market_value=item.market_value,
                    unrealized_pnl=item.unrealized_pnl,
                    unrealized_pnl_percent=item.unrealized_pnl_percent,
                    daily_pnl=item.daily_pnl,
                    month_to_date_pnl=item.month_to_date_pnl,
                    source=item.source,
                )
                for item in overview.positions
            ],
            notices=list(overview.notices),
            decision_reports=[
                AiSimulationDecisionResponse(
                    symbol=item.symbol,
                    display_name=item.display_name,
                    score=item.score,
                    decision=item.decision,
                    supportive_factor_count=item.supportive_factor_count,
                    adverse_factor_count=item.adverse_factor_count,
                    available_factor_ids=list(item.available_factor_ids),
                    unavailable_factor_ids=list(item.unavailable_factor_ids),
                    blockers=list(item.blockers),
                )
                for item in overview.decision_reports
            ],
        )


class TechnicalRequest(QuoteQuery):
    timeframe: BarTimeframe = BarTimeframe.DAILY
    limit: int = Field(default=180, ge=60, le=1_200)


class TechnicalResponse(BaseModel):
    symbol: str
    market: Market
    currency: str
    timeframe: BarTimeframe
    source: str
    bars: list[dict[str, object]]
    indicators: dict[str, object]
    volume_profile: dict[str, object]
    assessment: dict[str, object]


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


class DisciplineInput(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    symbol: str = Field(min_length=1, max_length=64)
    market: Market
    instrument_type: InstrumentType = InstrumentType.EQUITY
    buy_price: Decimal = Field(gt=0)
    add_price: Decimal | None = Field(default=None, gt=0)
    take_profit_price: Decimal = Field(gt=0)
    exit_price: Decimal = Field(gt=0)
    notes: str = Field(default="", max_length=4_000)
    status: DisciplineStatus = DisciplineStatus.ACTIVE


class DisciplineResponse(DisciplineInput):
    discipline_id: UUID
    version: int

    @classmethod
    def from_domain(cls, discipline: TradingDiscipline) -> DisciplineResponse:
        return cls(
            discipline_id=discipline.discipline_id,
            name=discipline.name,
            symbol=discipline.instrument.symbol,
            market=discipline.instrument.market,
            instrument_type=discipline.instrument.instrument_type,
            buy_price=discipline.buy_price,
            add_price=discipline.add_price,
            take_profit_price=discipline.take_profit_price,
            exit_price=discipline.exit_price,
            notes=discipline.notes,
            status=discipline.status,
            version=discipline.version,
        )


_DISCIPLINE_DECISION_LABELS: dict[DisciplineDecisionStatus, str] = {
    DisciplineDecisionStatus.OBSERVE: "观察",
    DisciplineDecisionStatus.BUY_CANDIDATE: "可考虑买入",
    DisciplineDecisionStatus.ADD_CONDITION_MET: "加仓条件满足",
    DisciplineDecisionStatus.TAKE_PROFIT: "止盈",
    DisciplineDecisionStatus.EXIT: "清仓",
}


class DisciplineDecisionResponse(BaseModel):
    """One deterministic status, separate from any generative AI explanation."""

    discipline_id: UUID
    discipline_name: str
    symbol: str
    market: Market
    instrument_type: InstrumentType
    status: DisciplineDecisionStatus
    label: str
    last_price: Decimal
    matched_level: Decimal | None
    rationale: str

    @classmethod
    def from_domain(cls, decision: DisciplineDecision) -> DisciplineDecisionResponse:
        discipline = decision.discipline
        price = decision.last_price
        label = _DISCIPLINE_DECISION_LABELS[decision.status]
        rationale = {
            DisciplineDecisionStatus.EXIT: (
                f"现价 {price} 已触及或低于清仓价 {discipline.exit_price}。"
            ),
            DisciplineDecisionStatus.TAKE_PROFIT: (
                f"现价 {price} 已触及或高于止盈价 {discipline.take_profit_price}。"
            ),
            DisciplineDecisionStatus.ADD_CONDITION_MET: (
                f"现价 {price} 已触及或高于加仓价 {discipline.add_price}，"
                f"但尚未触及止盈价 {discipline.take_profit_price}。"
            ),
            DisciplineDecisionStatus.BUY_CANDIDATE: (
                f"现价 {price} 处于清仓价 {discipline.exit_price} 之上，"
                f"且已触及或低于买入价 {discipline.buy_price}。"
            ),
            DisciplineDecisionStatus.OBSERVE: (
                f"现价 {price} 位于买入价 {discipline.buy_price} 与"
                f"加仓价 {discipline.add_price or discipline.take_profit_price} 之间，"
                "尚未满足已定义的价位条件。"
            ),
        }[decision.status]
        return cls(
            discipline_id=discipline.discipline_id,
            discipline_name=discipline.name,
            symbol=discipline.instrument.symbol,
            market=discipline.instrument.market,
            instrument_type=discipline.instrument.instrument_type,
            status=decision.status,
            label=label,
            last_price=price,
            matched_level=decision.matched_level,
            rationale=rationale,
        )
