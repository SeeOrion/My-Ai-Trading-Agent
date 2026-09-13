"""Pure allocation policy for the transparent AI paper-trading simulator."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_DOWN, Decimal


@dataclass(frozen=True, slots=True)
class AiSimulationCandidate:
    symbol: str
    score: Decimal
    last_price: Decimal
    supportive_factor_count: int
    adverse_factor_count: int
    available_factor_ids: tuple[str, ...]
    rationale: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class AiSimulationAllocation:
    symbol: str
    quantity: Decimal
    amount: Decimal
    allocation_percent: Decimal
    rationale: tuple[str, ...]


def choose_simulated_entry(
    candidate: AiSimulationCandidate,
    *,
    available_cash: Decimal,
    initial_capital: Decimal,
    open_position_count: int,
    max_positions: int,
    max_position_percent: Decimal,
    lot_size: Decimal,
) -> AiSimulationAllocation | None:
    """Apply a conservative trend/quality/risk-budget policy without execution.

    A buy requires a strong ranked candidate plus more supportive than adverse
    observed factors.  Cash is split across remaining slots and capped by the
    active strategy's position limit.  It is deliberately deterministic and
    auditable instead of presenting a black-box recommendation as a trade.
    """
    if available_cash <= 0 or initial_capital <= 0 or open_position_count >= max_positions:
        return None
    if candidate.last_price <= 0 or candidate.score < Decimal("70"):
        return None
    if candidate.supportive_factor_count <= candidate.adverse_factor_count:
        return None
    if not candidate.available_factor_ids:
        return None
    if lot_size <= 0 or not Decimal("0") < max_position_percent <= Decimal("100"):
        raise ValueError("invalid allocation constraints")

    remaining_slots = Decimal(max_positions - open_position_count)
    diversified_budget = available_cash / remaining_slots
    strategy_budget = initial_capital * max_position_percent / Decimal("100")
    amount_cap = min(diversified_budget, strategy_budget, available_cash)
    whole_lots = (amount_cap / candidate.last_price / lot_size).to_integral_value(
        rounding=ROUND_DOWN
    )
    quantity = whole_lots * lot_size
    if quantity <= 0:
        return None
    amount = quantity * candidate.last_price
    return AiSimulationAllocation(
        symbol=candidate.symbol,
        quantity=quantity,
        amount=amount,
        allocation_percent=amount / initial_capital * Decimal("100"),
        rationale=(
            f"候选综合评分 {candidate.score}/100，达到模拟建仓阈值 70。",
            (
                f"已观测因子中支持 {candidate.supportive_factor_count} 项、"
                f"逆风 {candidate.adverse_factor_count} 项。"
            ),
            (
                "按剩余槽位分散和单标的上限分配 "
                f"{amount / initial_capital * Decimal('100'):.2f}% 本金。"
            ),
            *candidate.rationale,
        ),
    )
