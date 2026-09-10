"""HTTP request and response contracts; no infrastructure calls occur here."""

from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from ai_trading_agent.domain.ability.factors import FactorMetadata
from ai_trading_agent.domain.aggregate.candidate import RankedCandidate
from ai_trading_agent.domain.aggregate.discipline import TradingDiscipline
from ai_trading_agent.domain.aggregate.discipline_decision import DisciplineDecision
from ai_trading_agent.domain.aggregate.market import Quote
from ai_trading_agent.domain.aggregate.market_brief import PostMarketBrief
from ai_trading_agent.domain.aggregate.market_scan import MarketScanRun
from ai_trading_agent.domain.aggregate.strategy import StrategyProfile
from ai_trading_agent.domain.aggregate.watchlist import (
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

    @classmethod
    def from_domain(cls, item: WatchlistItem) -> WatchlistResponse:
        return cls(
            item_id=item.item_id,
            symbol=item.instrument.symbol,
            market=item.instrument.market,
            instrument_type=item.instrument.instrument_type,
            label=item.label,
            notes=item.notes,
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

    @classmethod
    def from_domain(cls, position: PaperPosition) -> PaperPositionResponse:
        return cls(
            position_id=position.position_id,
            symbol=position.instrument.symbol,
            market=position.instrument.market,
            instrument_type=position.instrument.instrument_type,
            quantity=position.quantity,
            average_cost=position.average_cost,
            notes=position.notes,
        )


class PaperPositionValuationResponse(PaperPositionResponse):
    last_price: Decimal
    currency: str
    observed_at: str
    source: str
    market_value: Decimal
    unrealized_pnl: Decimal
    unrealized_pnl_percent: Decimal

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
