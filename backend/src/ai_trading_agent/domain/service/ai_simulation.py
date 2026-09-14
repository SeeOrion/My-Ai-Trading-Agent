"""Pure allocation policy for the transparent AI paper-trading simulator."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_DOWN, Decimal
from uuid import UUID

from ai_trading_agent.domain.aggregate.ai_simulation import AiSimulationPortfolio


@dataclass(frozen=True, slots=True)
class AiSimulationCandidate:
    symbol: str
    display_name: str
    score: Decimal
    last_price: Decimal
    supportive_factor_count: int
    adverse_factor_count: int
    available_factor_ids: tuple[str, ...]
    unavailable_factor_ids: tuple[str, ...]
    rationale: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class AiSimulationAllocation:
    symbol: str
    quantity: Decimal
    amount: Decimal
    allocation_percent: Decimal
    rationale: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class AiSimulationEntryDecision:
    allocation: AiSimulationAllocation | None
    blockers: tuple[str, ...]


def reconfigure_simulation_portfolio(
    portfolio: AiSimulationPortfolio,
    *,
    initial_capital: Decimal,
    max_positions: int,
    strategy_id: UUID | None,
    open_position_count: int,
) -> AiSimulationPortfolio:
    """Update account settings without discarding audited paper-trading state.

    Changing the starting capital is treated as a deposit or withdrawal.  The
    cash delta is applied while existing positions and their trade history stay
    intact, so historical simulated results remain explainable.
    """
    if open_position_count < 0:
        raise ValueError("open_position_count must not be negative")
    if max_positions < open_position_count:
        raise ValueError(
            f"当前已有 {open_position_count} 个 AI 模拟持仓，最多持仓不能低于该数量。"
        )

    updated_cash = portfolio.cash_balance + (initial_capital - portfolio.initial_capital)
    if updated_cash < 0:
        minimum_capital = portfolio.initial_capital - portfolio.cash_balance
        raise ValueError(
            "为保留已有模拟持仓与交易记录，初始本金不能低于 "
            f"{minimum_capital:.2f}。"
        )
    return AiSimulationPortfolio(
        portfolio_id=portfolio.portfolio_id,
        market=portfolio.market,
        currency=portfolio.currency,
        initial_capital=initial_capital,
        cash_balance=updated_cash,
        max_positions=max_positions,
        strategy_id=strategy_id,
        status=portfolio.status,
    )


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
    return evaluate_simulated_entry(
        candidate,
        available_cash=available_cash,
        initial_capital=initial_capital,
        open_position_count=open_position_count,
        max_positions=max_positions,
        max_position_percent=max_position_percent,
        lot_size=lot_size,
    ).allocation


def evaluate_simulated_entry(
    candidate: AiSimulationCandidate,
    *,
    available_cash: Decimal,
    initial_capital: Decimal,
    open_position_count: int,
    max_positions: int,
    max_position_percent: Decimal,
    lot_size: Decimal,
) -> AiSimulationEntryDecision:
    """Return an allocation or explicit, user-facing reasons for keeping cash."""
    blockers: list[str] = []
    if available_cash <= 0:
        blockers.append("可用现金为零，风险预算无法创建新的模拟仓位。")
    if initial_capital <= 0:
        blockers.append("初始本金无效，无法计算风险预算。")
    if open_position_count >= max_positions:
        blockers.append(f"持仓数已达到上限 {max_positions}，为保持分散化不再建仓。")
    if candidate.last_price <= 0:
        blockers.append("最新行情价格无效，无法计算模拟买入数量。")
    if candidate.score < Decimal("70"):
        blockers.append(f"候选评分 {candidate.score}/100，低于建仓阈值 70。")
    if candidate.adverse_factor_count > 0:
        blockers.append(
            "已计算的因子存在不利方向，保守规则不创建模拟仓位："
            f"支持 {candidate.supportive_factor_count} 项，"
            f"逆风 {candidate.adverse_factor_count} 项。"
        )
    if lot_size <= 0 or not Decimal("0") < max_position_percent <= Decimal("100"):
        raise ValueError("invalid allocation constraints")
    if blockers:
        return AiSimulationEntryDecision(None, tuple(blockers))

    remaining_slots = Decimal(max_positions - open_position_count)
    diversified_budget = available_cash / remaining_slots
    strategy_budget = initial_capital * max_position_percent / Decimal("100")
    amount_cap = min(diversified_budget, strategy_budget, available_cash)
    whole_lots = (amount_cap / candidate.last_price / lot_size).to_integral_value(
        rounding=ROUND_DOWN
    )
    quantity = whole_lots * lot_size
    if quantity <= 0:
        return AiSimulationEntryDecision(
            None,
            (
                "风险预算不足以覆盖最小交易单位："
                f"当前价格 {candidate.last_price}，最小单位 {lot_size}，"
                f"本次可分配预算 {amount_cap:.2f}。",
            ),
        )
    amount = quantity * candidate.last_price
    return AiSimulationEntryDecision(
        AiSimulationAllocation(
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
        ),
        (),
    )
