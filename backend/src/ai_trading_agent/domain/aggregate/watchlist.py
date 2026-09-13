"""Personal watchlist and paper-position aggregates; never broker state."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import UUID

from ai_trading_agent.domain.aggregate.market import Instrument, Quote


@dataclass(frozen=True, slots=True)
class WatchlistItem:
    item_id: UUID
    instrument: Instrument
    label: str = ""
    notes: str = ""

    def __post_init__(self) -> None:
        if len(self.label) > 160 or len(self.notes) > 4_000:
            raise ValueError("watchlist text exceeds the allowed length")


@dataclass(frozen=True, slots=True)
class PaperPosition:
    position_id: UUID
    instrument: Instrument
    quantity: Decimal
    average_cost: Decimal
    notes: str = ""

    def __post_init__(self) -> None:
        if self.quantity <= 0 or self.average_cost <= 0:
            raise ValueError("paper position quantity and average_cost must be positive")
        if len(self.notes) > 4_000:
            raise ValueError("notes must contain at most 4000 characters")

    @property
    def cost_basis(self) -> Decimal:
        return self.quantity * self.average_cost


@dataclass(frozen=True, slots=True)
class PaperPositionValuation:
    position: PaperPosition
    quote: Quote
    market_value: Decimal
    unrealized_pnl: Decimal
    unrealized_pnl_percent: Decimal
    daily_pnl: Decimal | None = None
    daily_pnl_percent: Decimal | None = None
    month_to_date_pnl: Decimal | None = None
    month_to_date_pnl_percent: Decimal | None = None
    month_reference_date: date | None = None


@dataclass(frozen=True, slots=True)
class PaperPortfolioCurrencySummary:
    """A currency-isolated total for manually entered paper positions."""

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

    def __post_init__(self) -> None:
        if self.position_count <= 0:
            raise ValueError("portfolio summary requires at least one position")
        if self.initial_principal <= 0 or self.total_market_value < 0:
            raise ValueError("portfolio value fields are invalid")
        if self.daily_coverage_count < 0 or self.month_coverage_count < 0:
            raise ValueError("portfolio coverage counts must not be negative")
        object.__setattr__(self, "currency", self.currency.strip().upper())


@dataclass(frozen=True, slots=True)
class PaperPortfolioSummary:
    """Latest paper-portfolio totals, deliberately separated by currency."""

    observed_at: datetime
    currencies: tuple[PaperPortfolioCurrencySummary, ...]
    valued_position_count: int
    total_position_count: int

    def __post_init__(self) -> None:
        if self.observed_at.tzinfo is None:
            raise ValueError("portfolio summary observation must be timezone-aware")
        if self.valued_position_count < 0 or self.total_position_count < 0:
            raise ValueError("portfolio summary counts must not be negative")
        if self.valued_position_count > self.total_position_count:
            raise ValueError("valued positions cannot exceed total positions")
        object.__setattr__(self, "observed_at", self.observed_at.astimezone(UTC))


@dataclass(frozen=True, slots=True)
class PaperPortfolioOverview:
    """One bounded refresh result for the manual paper portfolio."""

    valuations: tuple[PaperPositionValuation, ...]
    summary: PaperPortfolioSummary
    notices: tuple[str, ...] = ()


def value_paper_position(
    position: PaperPosition,
    quote: Quote,
    *,
    month_reference_close: Decimal | None = None,
    month_reference_date: date | None = None,
) -> PaperPositionValuation:
    if quote.instrument != position.instrument:
        raise ValueError("quote instrument must match the paper position")
    market_value = position.quantity * quote.last_price
    unrealized_pnl = market_value - position.cost_basis
    daily_pnl = None
    daily_pnl_percent = None
    if quote.previous_close is not None and quote.previous_close > 0:
        previous_value = position.quantity * quote.previous_close
        daily_pnl = market_value - previous_value
        daily_pnl_percent = daily_pnl / previous_value * Decimal("100")
    month_to_date_pnl = None
    month_to_date_pnl_percent = None
    if month_reference_close is not None and month_reference_close > 0:
        month_reference_value = position.quantity * month_reference_close
        month_to_date_pnl = market_value - month_reference_value
        month_to_date_pnl_percent = month_to_date_pnl / month_reference_value * Decimal("100")
    return PaperPositionValuation(
        position=position,
        quote=quote,
        market_value=market_value,
        unrealized_pnl=unrealized_pnl,
        unrealized_pnl_percent=(unrealized_pnl / position.cost_basis * Decimal("100")),
        daily_pnl=daily_pnl,
        daily_pnl_percent=daily_pnl_percent,
        month_to_date_pnl=month_to_date_pnl,
        month_to_date_pnl_percent=month_to_date_pnl_percent,
        month_reference_date=month_reference_date if month_to_date_pnl is not None else None,
    )


def summarize_paper_portfolio(
    valuations: tuple[PaperPositionValuation, ...],
    *,
    observed_at: datetime,
    total_position_count: int,
) -> PaperPortfolioSummary:
    """Aggregate same-currency values without fabricating FX conversions.

    A daily or monthly total is omitted if any valued position in that currency
    lacks its required reference price.  Presenting a partial return as a
    portfolio return would be misleading.
    """
    grouped: dict[str, list[PaperPositionValuation]] = {}
    for valuation in valuations:
        grouped.setdefault(valuation.quote.instrument.currency, []).append(valuation)

    summaries = tuple(
        _currency_summary(currency, tuple(items))
        for currency, items in sorted(grouped.items())
    )
    return PaperPortfolioSummary(
        observed_at=observed_at,
        currencies=summaries,
        valued_position_count=len(valuations),
        total_position_count=total_position_count,
    )


def _currency_summary(
    currency: str, valuations: tuple[PaperPositionValuation, ...]
) -> PaperPortfolioCurrencySummary:
    initial_principal = sum((item.position.cost_basis for item in valuations), Decimal("0"))
    total_market_value = sum((item.market_value for item in valuations), Decimal("0"))
    cumulative_pnl = total_market_value - initial_principal
    daily_values = tuple(item.daily_pnl for item in valuations)
    monthly_values = tuple(item.month_to_date_pnl for item in valuations)
    daily_pnl = _complete_total(daily_values)
    month_to_date_pnl = _complete_total(monthly_values)
    daily_base = sum(
        (
            item.position.quantity * item.quote.previous_close
            for item in valuations
            if item.quote.previous_close is not None
        ),
        Decimal("0"),
    )
    monthly_base = total_market_value - month_to_date_pnl if month_to_date_pnl is not None else None
    return PaperPortfolioCurrencySummary(
        currency=currency,
        position_count=len(valuations),
        initial_principal=initial_principal,
        total_market_value=total_market_value,
        cumulative_pnl=cumulative_pnl,
        cumulative_return_percent=cumulative_pnl / initial_principal * Decimal("100"),
        daily_pnl=daily_pnl,
        daily_return_percent=(
            daily_pnl / daily_base * Decimal("100")
            if daily_pnl is not None and daily_base > 0
            else None
        ),
        month_to_date_pnl=month_to_date_pnl,
        month_to_date_return_percent=(
            month_to_date_pnl / monthly_base * Decimal("100")
            if month_to_date_pnl is not None and monthly_base is not None and monthly_base > 0
            else None
        ),
        daily_coverage_count=sum(value is not None for value in daily_values),
        month_coverage_count=sum(value is not None for value in monthly_values),
    )


def _complete_total(values: tuple[Decimal | None, ...]) -> Decimal | None:
    if not values or any(value is None for value in values):
        return None
    return sum((value for value in values if value is not None), Decimal("0"))
