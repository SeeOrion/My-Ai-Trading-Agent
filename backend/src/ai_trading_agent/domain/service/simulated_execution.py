"""Deterministic execution assumptions for paper trades.

This module deliberately models an *estimate*, not a broker fill.  Keeping it
pure makes the assumptions visible in every simulated trade and prevents a
research result from being mistaken for a real order.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_DOWN, Decimal

from ai_trading_agent.domain.aggregate.market import Instrument
from ai_trading_agent.domain.enums.market import InstrumentType, Market

# These are deliberately modest planning assumptions, not venue fee schedules.
# They include a small adverse fill allowance and an all-in transaction-cost
# estimate so a paper account does not receive an unrealistically perfect fill.
DEFAULT_SLIPPAGE_BPS = Decimal("5")
DEFAULT_COST_BPS = Decimal("5")


@dataclass(frozen=True, slots=True)
class SimulatedExecutionEstimate:
    """The cash impact of one paper-market-order estimate."""

    side: str
    reference_price: Decimal
    fill_price: Decimal
    quantity: Decimal
    gross_amount: Decimal
    estimated_cost: Decimal

    def __post_init__(self) -> None:
        if self.side not in {"buy", "sell"}:
            raise ValueError("simulation side must be buy or sell")
        if self.reference_price <= 0 or self.fill_price <= 0 or self.quantity <= 0:
            raise ValueError("simulation execution values must be positive")
        if self.estimated_cost < 0:
            raise ValueError("estimated_cost must not be negative")

    @property
    def cash_required(self) -> Decimal:
        """Cash debited for a simulated buy, including the estimate of costs."""
        if self.side != "buy":
            raise ValueError("cash_required applies only to buys")
        return self.gross_amount + self.estimated_cost

    @property
    def cash_proceeds(self) -> Decimal:
        """Cash credited for a simulated sale, net of the estimate of costs."""
        if self.side != "sell":
            raise ValueError("cash_proceeds applies only to sells")
        return self.gross_amount - self.estimated_cost

    @property
    def rationale(self) -> tuple[str, ...]:
        return (
            (
                f"模拟成交口径：参考价 {self.reference_price:.4f}，"
                f"按 {DEFAULT_SLIPPAGE_BPS}bp 不利滑点估算成交价 {self.fill_price:.4f}。"
            ),
            f"估算交易成本 {self.estimated_cost:.2f}（{DEFAULT_COST_BPS}bp），不代表券商实际费用。",
        )


def minimum_trade_unit(instrument: Instrument) -> Decimal:
    """Return a conservative whole-unit convention for the supported markets."""
    if instrument.market is Market.FUND or instrument.instrument_type is InstrumentType.FUND:
        raise ValueError("场外基金按净值确认，当前不支持盘中模拟成交。")
    if instrument.market is Market.A_SHARE:
        # The project currently models A-share stocks and on-exchange ETFs with
        # whole lots.  Venue-specific odd-lot liquidation is intentionally not
        # assumed in a general simulator.
        return Decimal("100")
    return Decimal("1")


def estimate_simulated_execution(
    *,
    side: str,
    reference_price: Decimal,
    quantity: Decimal,
) -> SimulatedExecutionEstimate:
    """Estimate adverse slippage and costs from a fresh, positive quote."""
    if side not in {"buy", "sell"}:
        raise ValueError("simulation side must be buy or sell")
    if reference_price <= 0 or quantity <= 0:
        raise ValueError("reference_price and quantity must be positive")
    rate = DEFAULT_SLIPPAGE_BPS / Decimal("10000")
    fill_price = reference_price * (Decimal("1") + rate if side == "buy" else Decimal("1") - rate)
    gross_amount = fill_price * quantity
    estimated_cost = gross_amount * DEFAULT_COST_BPS / Decimal("10000")
    return SimulatedExecutionEstimate(
        side=side,
        reference_price=reference_price,
        fill_price=fill_price,
        quantity=quantity,
        gross_amount=gross_amount,
        estimated_cost=estimated_cost,
    )


def quantity_for_cash_budget(
    *,
    cash_budget: Decimal,
    reference_price: Decimal,
    lot_size: Decimal,
) -> Decimal:
    """Fit a buy into its cash budget using the same execution assumptions."""
    if cash_budget <= 0 or reference_price <= 0 or lot_size <= 0:
        return Decimal("0")
    one_lot = estimate_simulated_execution(
        side="buy", reference_price=reference_price, quantity=lot_size
    )
    lots = (cash_budget / one_lot.cash_required).to_integral_value(rounding=ROUND_DOWN)
    return lots * lot_size


def quantity_for_partial_exit(quantity: Decimal, lot_size: Decimal) -> Decimal:
    """Take half a position where possible, using a valid whole trade unit."""
    if quantity <= 0 or lot_size <= 0:
        raise ValueError("quantity and lot_size must be positive")
    half_lots = ((quantity / Decimal("2")) / lot_size).to_integral_value(rounding=ROUND_DOWN)
    return quantity if half_lots <= 0 else half_lots * lot_size
