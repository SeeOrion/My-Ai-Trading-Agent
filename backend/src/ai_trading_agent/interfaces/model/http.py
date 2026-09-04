"""HTTP request and response contracts; no infrastructure calls occur here."""

from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from ai_trading_agent.domain.ability.factors import FactorMetadata
from ai_trading_agent.domain.aggregate.candidate import RankedCandidate
from ai_trading_agent.domain.aggregate.discipline import TradingDiscipline
from ai_trading_agent.domain.aggregate.market import Quote
from ai_trading_agent.domain.aggregate.strategy import StrategyProfile
from ai_trading_agent.domain.enums.candidates import CandidateRanking
from ai_trading_agent.domain.enums.market import InstrumentType, Market
from ai_trading_agent.domain.enums.research import DisciplineStatus

DEFAULT_NEWS_SOURCES = ("eastmoney",)


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
