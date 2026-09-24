"""Deterministic, explainable exit rules for autonomous paper positions.

The rules model a reviewable paper-trading policy, never a broker order.  Price
protection works without optional research data; trend exits require multiple
available confirmations so a missing upstream field cannot become a sell signal.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from ai_trading_agent.domain.service.simulated_execution import quantity_for_partial_exit

HUNDRED = Decimal("100")
EXIT_POLICY_VERSION = "classic_v1"
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
    hard_stop_price = evidence.average_cost * (Decimal("1") - HARD_STOP_LOSS_PERCENT / HUNDRED)
    trailing_stop_price = _trailing_stop_price(evidence, high_watermark)

    if evidence.current_price <= hard_stop_price:
        return _decision(
            evidence,
            action="full_exit",
            quantity=evidence.quantity,
            reason_code="hard_stop_loss",
            rationale=(
                f"持仓收益率 {return_percent:.2f}% 已触及 "
                f"-{HARD_STOP_LOSS_PERCENT}% 最大亏损基线。",
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
                f"同时出现至少两项独立风险确认：{'、'.join(adverse_factors)}。",
            ),
            high_watermark=high_watermark,
            trailing_stop_price=trailing_stop_price,
        )

    if evidence.profit_take_stage == 0 and return_percent >= FIRST_PROFIT_TARGET_PERCENT:
        quantity = quantity_for_partial_exit(evidence.quantity, evidence.lot_size)
        action = "full_exit" if quantity >= evidence.quantity else "partial_exit"
        return _decision(
            evidence,
            action=action,
            quantity=quantity,
            reason_code="first_profit_target",
            rationale=(
                f"持仓收益率 {return_percent:.2f}% 已达到 {FIRST_PROFIT_TARGET_PERCENT}% "
                "首次盈利目标。",
                (
                    "按有效交易单位兑现约一半仓位，剩余仓位转入移动保护。"
                    if action == "partial_exit"
                    else "持仓不足以拆分为两个有效交易单位，因此全部模拟止盈。"
                ),
            ),
            high_watermark=high_watermark,
            trailing_stop_price=_trailing_stop_price(
                SimulationExitEvidence(
                    current_price=evidence.current_price,
                    average_cost=evidence.average_cost,
                    quantity=evidence.quantity,
                    highest_price=high_watermark,
                    profit_take_stage=1,
                    lot_size=evidence.lot_size,
                    atr_14=evidence.atr_14,
                    sma_20=evidence.sma_20,
                    factor_directions=evidence.factor_directions,
                ),
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
    return high_watermark * (Decimal("1") - distance_percent / HUNDRED)


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
        identifier
        for identifier, direction in factor_directions
        if identifier in _TREND_RISK_FACTORS and direction == "adverse"
    )
