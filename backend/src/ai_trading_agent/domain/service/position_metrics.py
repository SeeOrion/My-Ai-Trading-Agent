"""Pure, reusable cost and unrealized-profit calculations for a holding."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True, slots=True)
class PositionMetrics:
    """Cost and mark-to-market metrics independent of any broker or repository."""

    quantity: Decimal
    average_cost: Decimal
    cost_amount: Decimal
    market_price: Decimal | None
    market_value: Decimal | None
    unrealized_pnl: Decimal | None
    unrealized_pnl_percent: Decimal | None


def calculate_position_metrics(
    quantity: Decimal,
    average_cost: Decimal,
    *,
    market_price: Decimal | None = None,
) -> PositionMetrics:
    """Calculate one holding's cost and optional mark-to-market profit or loss.

    The function has no dependency on paper trading, a data source, or a database,
    so a future real-position or imported-trade use case can reuse it unchanged.
    """
    if quantity <= 0 or average_cost <= 0:
        raise ValueError("quantity and average_cost must be positive")
    if market_price is not None and market_price < 0:
        raise ValueError("market_price must not be negative")

    cost_amount = quantity * average_cost
    if market_price is None:
        return PositionMetrics(
            quantity=quantity,
            average_cost=average_cost,
            cost_amount=cost_amount,
            market_price=None,
            market_value=None,
            unrealized_pnl=None,
            unrealized_pnl_percent=None,
        )

    market_value = quantity * market_price
    unrealized_pnl = market_value - cost_amount
    return PositionMetrics(
        quantity=quantity,
        average_cost=average_cost,
        cost_amount=cost_amount,
        market_price=market_price,
        market_value=market_value,
        unrealized_pnl=unrealized_pnl,
        unrealized_pnl_percent=unrealized_pnl / cost_amount * Decimal("100"),
    )
