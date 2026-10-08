"""Deterministic, explainable exit rules for autonomous paper positions.

The rules model a reviewable paper-trading policy, never a broker order.  Price
protection works without optional research data; trend exits require multiple
available confirmations so a missing upstream field cannot become a sell signal.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime
from decimal import Decimal

from ai_trading_agent.domain.aggregate.exit_plan import PositionExitPlan
from ai_trading_agent.domain.service.simulated_execution import quantity_for_partial_exit

HUNDRED = Decimal("100")
EXIT_POLICY_VERSION = "adaptive_v2"
HARD_STOP_LOSS_PERCENT = Decimal("8")
FIRST_PROFIT_TARGET_PERCENT = Decimal("20")
DEFAULT_TRAILING_DISTANCE_PERCENT = Decimal("8")
MIN_TRAILING_DISTANCE_PERCENT = Decimal("5")
MAX_TRAILING_DISTANCE_PERCENT = Decimal("12")
ATR_TRAILING_MULTIPLIER = Decimal("2")
MIN_TREND_EXIT_CONFIRMATIONS = 2

_TREND_RISK_FACTORS = frozenset(
    {
        "momentum_20d",
        "volatility_20d",
        "short_reversal_5d",
        "moving_average_trend",
        "relative_volume_20d",
        "news_sentiment",
    }
)


@dataclass(frozen=True, slots=True)
class SimulationExitEvidence:
    current_price: Decimal
    average_cost: Decimal
    quantity: Decimal
    highest_price: Decimal
    profit_take_stage: int
    lot_size: Decimal
    atr_14: Decimal | None = None
    sma_20: Decimal | None = None
    factor_directions: tuple[tuple[str, str], ...] = ()
    stop_price: Decimal | None = None
    target_price: Decimal | None = None
    previous_trailing_stop: Decimal | None = None
    fresh_flow_out: bool = False

    def __post_init__(self) -> None:
        if (
            min(
                self.current_price,
                self.average_cost,
                self.quantity,
                self.highest_price,
                self.lot_size,
            )
            <= 0
        ):
            raise ValueError("exit evidence price, quantity and lot size must be positive")
        if self.profit_take_stage not in {0, 1}:
            raise ValueError("profit_take_stage must be 0 or 1")
        if self.atr_14 is not None and self.atr_14 <= 0:
            raise ValueError("atr_14 must be positive when provided")
        if self.sma_20 is not None and self.sma_20 <= 0:
            raise ValueError("sma_20 must be positive when provided")


@dataclass(frozen=True, slots=True)
class SimulationExitDecision:
    action: str
    quantity: Decimal
    reason_code: str
    rationale: tuple[str, ...]
    highest_price: Decimal
    profit_take_stage: int
    trailing_stop_price: Decimal | None

    def __post_init__(self) -> None:
        if self.action not in {"hold", "partial_exit", "full_exit"}:
            raise ValueError("invalid simulation exit action")
        if self.quantity < 0:
            raise ValueError("exit quantity must not be negative")
        if self.action == "hold" and self.quantity != 0:
            raise ValueError("hold decisions cannot have an exit quantity")
        if self.action != "hold" and self.quantity <= 0:
            raise ValueError("exit decisions require a positive quantity")
        if not self.reason_code.strip() or not self.rationale:
            raise ValueError("exit decisions require an auditable reason")


def evaluate_simulation_exit(evidence: SimulationExitEvidence) -> SimulationExitDecision:
    """Apply price protection, profit capture and confirmed trend deterioration."""
    high_watermark = max(evidence.highest_price, evidence.current_price)
    return_percent = ((evidence.current_price / evidence.average_cost) - Decimal("1")) * HUNDRED
    hard_stop_price = evidence.stop_price or evidence.average_cost * (
        Decimal("1") - HARD_STOP_LOSS_PERCENT / HUNDRED
    )
    target_price = evidence.target_price or evidence.average_cost * (
        Decimal("1") + FIRST_PROFIT_TARGET_PERCENT / HUNDRED
    )
    trailing_stop_price = _trailing_stop_price(evidence, high_watermark)

    if evidence.current_price <= hard_stop_price:
        return _decision(
            evidence,
            action="full_exit",
            quantity=evidence.quantity,
            reason_code="hard_stop_loss",
            rationale=(
                f"持仓收益率 {return_percent:.2f}% 已触及 本仓位已记录的风险保护线。",
                f"成本 {evidence.average_cost:.4f}，风险保护价 {hard_stop_price:.4f}。",
            ),
            high_watermark=high_watermark,
            trailing_stop_price=trailing_stop_price,
        )

    if (
        evidence.profit_take_stage == 1
        and trailing_stop_price is not None
        and evidence.current_price <= trailing_stop_price
    ):
        drawdown = (evidence.current_price / high_watermark - Decimal("1")) * HUNDRED
        return _decision(
            evidence,
            action="full_exit",
            quantity=evidence.quantity,
            reason_code="trailing_profit_stop",
            rationale=(
                f"剩余仓位从高水位 {high_watermark:.4f} 回撤 {drawdown:.2f}%，"
                f"已触及移动保护价 {trailing_stop_price:.4f}。",
                _trailing_basis(evidence, high_watermark),
            ),
            high_watermark=high_watermark,
            trailing_stop_price=trailing_stop_price,
        )

    adverse_factors = _confirmed_adverse_factors(evidence.factor_directions)
    if (
        evidence.sma_20 is not None
        and evidence.current_price < evidence.sma_20
        and len(adverse_factors) >= MIN_TREND_EXIT_CONFIRMATIONS
    ):
        return _decision(
            evidence,
            action="full_exit",
            quantity=evidence.quantity,
            reason_code="confirmed_trend_breakdown",
            rationale=(
                f"现价 {evidence.current_price:.4f} 已跌破 20 日均线 {evidence.sma_20:.4f}。",
                f"同时出现至少两项技术风险确认：{'、'.join(adverse_factors)}。",
            ),
            high_watermark=high_watermark,
            trailing_stop_price=trailing_stop_price,
        )

    if evidence.profit_take_stage == 0 and evidence.current_price >= target_price:
        quantity = quantity_for_partial_exit(evidence.quantity, evidence.lot_size)
        action = "full_exit" if quantity >= evidence.quantity else "partial_exit"
        return _decision(
            evidence,
            action=action,
            quantity=quantity,
            reason_code="first_profit_target",
            rationale=(
                f"持仓收益率 {return_percent:.2f}%，现价已达到记录的止盈价 {target_price:.4f}。",
                (
                    "按有效交易单位兑现约一半仓位，剩余仓位转入移动保护。"
                    if action == "partial_exit"
                    else "持仓不足以拆分为两个有效交易单位，因此全部模拟止盈。"
                ),
            ),
            high_watermark=high_watermark,
            trailing_stop_price=_trailing_stop_price(
                replace(evidence, highest_price=high_watermark, profit_take_stage=1),
                high_watermark,
            ),
            profit_take_stage=1,
        )

    return _decision(
        evidence,
        action="hold",
        quantity=Decimal("0"),
        reason_code="risk_conditions_not_met",
        rationale=(
            f"持仓收益率 {return_percent:.2f}%，尚未触及硬止损、盈利兑现或多因子趋势退出条件。",
        ),
        high_watermark=high_watermark,
        trailing_stop_price=trailing_stop_price,
    )


def _decision(
    evidence: SimulationExitEvidence,
    *,
    action: str,
    quantity: Decimal,
    reason_code: str,
    rationale: tuple[str, ...],
    high_watermark: Decimal,
    trailing_stop_price: Decimal | None,
    profit_take_stage: int | None = None,
) -> SimulationExitDecision:
    return SimulationExitDecision(
        action=action,
        quantity=quantity,
        reason_code=reason_code,
        rationale=rationale,
        highest_price=high_watermark,
        profit_take_stage=(
            evidence.profit_take_stage if profit_take_stage is None else profit_take_stage
        ),
        trailing_stop_price=trailing_stop_price,
    )


def _trailing_stop_price(
    evidence: SimulationExitEvidence, high_watermark: Decimal
) -> Decimal | None:
    if evidence.profit_take_stage == 0:
        return None
    distance_percent = DEFAULT_TRAILING_DISTANCE_PERCENT
    if evidence.atr_14 is not None:
        distance_percent = evidence.atr_14 * ATR_TRAILING_MULTIPLIER / high_watermark * HUNDRED
        distance_percent = min(
            MAX_TRAILING_DISTANCE_PERCENT,
            max(MIN_TRAILING_DISTANCE_PERCENT, distance_percent),
        )
    return max(
        evidence.previous_trailing_stop or Decimal("0"),
        high_watermark * (Decimal("1") - distance_percent / HUNDRED),
    )


def review_exit_plan(
    evidence: SimulationExitEvidence,
    previous: PositionExitPlan | None,
    reviewed_at: datetime,
    *,
    fresh_flow_out: bool = False,
    data_notes: tuple[str, ...] = (),
) -> PositionExitPlan:
    """Set entry risk at 2 ATR (4–8%) and 2R target; never loosen existing stops.

    Multiple technical risks plus same-day institutional/total outflow tighten
    protection. Missing or stale research cannot create negative evidence.
    """
    risk = Decimal("0.08")
    if evidence.atr_14 is not None:
        risk = min(
            Decimal("0.08"), max(Decimal("0.04"), evidence.atr_14 * 2 / evidence.average_cost)
        )
    stop = evidence.average_cost * (1 - risk)
    target = evidence.average_cost * (1 + risk * 2)
    basis = ["入场风险采用 2×ATR，限制在成本的 4%–8%；首批止盈设为初始风险的两倍。"]
    if evidence.atr_14 is None:
        basis.append("ATR 暂缺：使用 8% 风险距离和 16% 首批止盈作为明确的降级计划。")
    if previous:
        stop = max(previous.stop_price, stop)
        target = previous.target_price
        basis.append("已设止损只收紧；首次止盈价保持原计划，避免不断追高目标。")
    adverse = _confirmed_adverse_factors(evidence.factor_directions)
    if fresh_flow_out and len(adverse) >= 2:
        stop = max(stop, evidence.current_price * Decimal("0.97"))
        basis.append("当日资金净流出且至少两项技术因子转弱，收紧保护至现价下方 3%。")
    if evidence.previous_trailing_stop is not None:
        stop = max(stop, evidence.previous_trailing_stop)
    return PositionExitPlan(stop, target, reviewed_at, basis=tuple(basis), data_notes=data_notes)


def _trailing_basis(evidence: SimulationExitEvidence, high_watermark: Decimal) -> str:
    if evidence.atr_14 is None:
        return f"无可用 ATR 时使用 {DEFAULT_TRAILING_DISTANCE_PERCENT}% 回撤基线。"
    raw_distance = evidence.atr_14 * ATR_TRAILING_MULTIPLIER / high_watermark * HUNDRED
    applied = min(MAX_TRAILING_DISTANCE_PERCENT, max(MIN_TRAILING_DISTANCE_PERCENT, raw_distance))
    return (
        f"移动距离使用 2×ATR（ATR {evidence.atr_14:.4f}），"
        f"并限制在 {MIN_TRAILING_DISTANCE_PERCENT}%–{MAX_TRAILING_DISTANCE_PERCENT}%；"
        f"本次采用 {applied:.2f}%。"
    )


def _confirmed_adverse_factors(
    factor_directions: tuple[tuple[str, str], ...],
) -> tuple[str, ...]:
    return tuple(
        dict.fromkeys(
            identifier
            for identifier, direction in factor_directions
            if identifier in _TREND_RISK_FACTORS and direction == "adverse"
        )
    )
