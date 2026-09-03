"""Research bounded context: deterministic analyses over provider-neutral data."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from ai_trading_agent.domain.aggregate.market import Instrument
from ai_trading_agent.domain.enums.research import (
    FlowDirection,
    OptionKind,
    PositionSide,
    SentimentLabel,
)

ZERO = Decimal("0")


@dataclass(frozen=True, slots=True)
class FinancialSnapshot:
    """Published financial facts; unavailable metrics remain ``None``."""

    instrument: Instrument
    announced_on: date
    report_period: date
    eps: Decimal | None = None
    return_on_equity_pct: Decimal | None = None
    gross_margin_pct: Decimal | None = None
    current_ratio: Decimal | None = None
    net_profit_growth_pct: Decimal | None = None
    price_to_earnings: Decimal | None = None
    price_to_book: Decimal | None = None
    source: str = ""

    def __post_init__(self) -> None:
        if not self.source.strip():
            raise ValueError("source must not be empty")
        if self.report_period > self.announced_on:
            raise ValueError("report_period must not be later than announced_on")


@dataclass(frozen=True, slots=True)
class FundamentalAssessment:
    snapshot: FinancialSnapshot
    score: int
    observations: tuple[str, ...]


def assess_fundamentals(snapshot: FinancialSnapshot) -> FundamentalAssessment:
    """Apply a transparent, non-predictive quality screen to published facts."""
    score = 0
    observations: list[str] = []
    if snapshot.return_on_equity_pct is not None:
        if snapshot.return_on_equity_pct >= Decimal("15"):
            score += 2
            observations.append("return on equity is at least 15%")
        elif snapshot.return_on_equity_pct >= Decimal("8"):
            score += 1
            observations.append("return on equity is at least 8%")
    if snapshot.gross_margin_pct is not None and snapshot.gross_margin_pct >= Decimal("30"):
        score += 1
        observations.append("gross margin is at least 30%")
    if snapshot.current_ratio is not None:
        if snapshot.current_ratio >= Decimal("1.2"):
            score += 1
            observations.append("current ratio is at least 1.2")
        elif snapshot.current_ratio < Decimal("1"):
            score -= 1
            observations.append("current ratio is below 1")
    if snapshot.net_profit_growth_pct is not None:
        if snapshot.net_profit_growth_pct >= Decimal("10"):
            score += 1
            observations.append("net profit growth is at least 10%")
        elif snapshot.net_profit_growth_pct <= Decimal("-10"):
            score -= 1
            observations.append("net profit growth is at most -10%")
    if snapshot.price_to_earnings is not None:
        if ZERO < snapshot.price_to_earnings <= Decimal("30"):
            score += 1
            observations.append("positive price-to-earnings is no more than 30")
        elif snapshot.price_to_earnings > Decimal("80"):
            score -= 1
            observations.append("price-to-earnings is above 80")
    return FundamentalAssessment(snapshot, score, tuple(observations))


@dataclass(frozen=True, slots=True)
class CapitalFlowSnapshot:
    """One instrument's reported capital flow, normalized to CNY."""

    instrument: Instrument
    trade_date: date
    net_flow_cny: Decimal
    large_order_net_flow_cny: Decimal
    source: str

    def __post_init__(self) -> None:
        if not self.source.strip():
            raise ValueError("source must not be empty")


@dataclass(frozen=True, slots=True)
class CapitalFlowAssessment:
    snapshot: CapitalFlowSnapshot
    direction: FlowDirection
    institutional_direction: FlowDirection


def assess_capital_flow(snapshot: CapitalFlowSnapshot) -> CapitalFlowAssessment:
    return CapitalFlowAssessment(
        snapshot=snapshot,
        direction=_flow_direction(snapshot.net_flow_cny),
        institutional_direction=_flow_direction(snapshot.large_order_net_flow_cny),
    )


def _flow_direction(value: Decimal) -> FlowDirection:
    if value > ZERO:
        return FlowDirection.INFLOW
    if value < ZERO:
        return FlowDirection.OUTFLOW
    return FlowDirection.NEUTRAL


@dataclass(frozen=True, slots=True)
class SentimentAssessment:
    score: Decimal
    label: SentimentLabel
    positive_terms: tuple[str, ...]
    negative_terms: tuple[str, ...]


def analyze_financial_sentiment(text: str) -> SentimentAssessment:
    """Score text with a small explainable bilingual finance lexicon.

    This deterministic baseline is intentionally not an investment forecast;
    later provider adapters may replace it with a trained model behind a port.
    """
    normalized = text.lower()
    if not normalized.strip():
        raise ValueError("text must not be empty")
    positive_terms = tuple(term for term in _POSITIVE_TERMS if term in normalized)
    negative_terms = tuple(term for term in _NEGATIVE_TERMS if term in normalized)
    total = len(positive_terms) + len(negative_terms)
    score = (
        ZERO
        if total == 0
        else Decimal(len(positive_terms) - len(negative_terms)) / Decimal(total)
    )
    label = (
        SentimentLabel.POSITIVE
        if score >= Decimal("0.2")
        else SentimentLabel.NEGATIVE
        if score <= Decimal("-0.2")
        else SentimentLabel.NEUTRAL
    )
    return SentimentAssessment(score, label, positive_terms, negative_terms)


_POSITIVE_TERMS = (
    "beat",
    "upgrade",
    "growth",
    "profit",
    "buyback",
    "increase",
    "上涨",
    "超预期",
    "增长",
    "盈利",
    "回购",
    "上调",
)
_NEGATIVE_TERMS = (
    "miss",
    "downgrade",
    "loss",
    "decline",
    "warning",
    "lawsuit",
    "下跌",
    "低于预期",
    "亏损",
    "下降",
    "预警",
    "诉讼",
)


@dataclass(frozen=True, slots=True)
class OptionLeg:
    kind: OptionKind
    side: PositionSide
    strike: Decimal
    premium: Decimal
    multiplier: int = 100

    def __post_init__(self) -> None:
        if self.strike <= ZERO:
            raise ValueError("strike must be positive")
        if self.premium < ZERO:
            raise ValueError("premium must not be negative")
        if self.multiplier <= 0:
            raise ValueError("multiplier must be positive")

    def expiry_pnl(self, underlying_price: Decimal) -> Decimal:
        if underlying_price < ZERO:
            raise ValueError("underlying_price must not be negative")
        intrinsic = (
            max(underlying_price - self.strike, ZERO)
            if self.kind is OptionKind.CALL
            else max(self.strike - underlying_price, ZERO)
        )
        per_unit = intrinsic - self.premium
        multiplier = Decimal(self.multiplier)
        return per_unit * multiplier if self.side is PositionSide.LONG else -per_unit * multiplier


@dataclass(frozen=True, slots=True)
class OptionStrategy:
    legs: tuple[OptionLeg, ...]

    def __post_init__(self) -> None:
        if not self.legs:
            raise ValueError("an option strategy needs at least one leg")

    def expiry_pnl(self, underlying_price: Decimal) -> Decimal:
        return sum((leg.expiry_pnl(underlying_price) for leg in self.legs), start=ZERO)


@dataclass(frozen=True, slots=True)
class OptionStrategyAssessment:
    break_evens: tuple[Decimal, ...]
    maximum_profit: Decimal | None
    maximum_loss: Decimal | None


def assess_option_strategy(strategy: OptionStrategy) -> OptionStrategyAssessment:
    """Calculate expiry break-evens and bounded/unbounded P&L extrema."""
    strikes = sorted({leg.strike for leg in strategy.legs})
    boundaries = [ZERO, *strikes]
    values = [strategy.expiry_pnl(boundary) for boundary in boundaries]
    roots: set[Decimal] = set()
    for low, high in zip(boundaries, boundaries[1:], strict=False):
        root = _line_root(strategy, low, high)
        if root is not None:
            roots.add(root)
    tail_root = _line_root(strategy, boundaries[-1], None)
    if tail_root is not None:
        roots.add(tail_root)

    tail_slope = _interval_slope(strategy, boundaries[-1], None)
    maximum_profit = None if tail_slope > ZERO else max(values)
    maximum_loss = None if tail_slope < ZERO else min(values)
    return OptionStrategyAssessment(tuple(sorted(roots)), maximum_profit, maximum_loss)


def _line_root(strategy: OptionStrategy, low: Decimal, high: Decimal | None) -> Decimal | None:
    slope = _interval_slope(strategy, low, high)
    value_at_low = strategy.expiry_pnl(low)
    if slope == ZERO:
        return low if value_at_low == ZERO else None
    root = low - value_at_low / slope
    if root < low or (high is not None and root > high):
        return None
    return root


def _interval_slope(strategy: OptionStrategy, low: Decimal, high: Decimal | None) -> Decimal:
    slope = ZERO
    for leg in strategy.legs:
        sign = Decimal(leg.multiplier if leg.side is PositionSide.LONG else -leg.multiplier)
        if leg.kind is OptionKind.CALL and low >= leg.strike:
            slope += sign
        if leg.kind is OptionKind.PUT and high is not None and high <= leg.strike:
            slope -= sign
    return slope
