"""Personal watchlist and paper-position aggregates; never broker state."""

from __future__ import annotations

from dataclasses import dataclass
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


def value_paper_position(position: PaperPosition, quote: Quote) -> PaperPositionValuation:
    if quote.instrument != position.instrument:
        raise ValueError("quote instrument must match the paper position")
    market_value = position.quantity * quote.last_price
    unrealized_pnl = market_value - position.cost_basis
    return PaperPositionValuation(
        position=position,
        quote=quote,
        market_value=market_value,
        unrealized_pnl=unrealized_pnl,
        unrealized_pnl_percent=(unrealized_pnl / position.cost_basis * Decimal("100")),
    )
