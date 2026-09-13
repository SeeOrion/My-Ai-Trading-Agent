"""Pure reconciliation of factor evidence, strategies and personal price disciplines."""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from ai_trading_agent.domain.aggregate.discipline_decision import DisciplineDecision
from ai_trading_agent.domain.aggregate.manual_action import ManualActionAssessment
from ai_trading_agent.domain.aggregate.strategy import StrategyProfile
from ai_trading_agent.domain.enums.research import DisciplineDecisionStatus, ManualActionStatus


def assess_manual_action(
    factor_directions: Mapping[str, str],
    strategies: Sequence[StrategyProfile],
    discipline_decisions: Sequence[DisciplineDecision],
) -> ManualActionAssessment:
    """Prioritize user risk limits, then require an aligned active strategy for entry.

    An exit or take-profit level deliberately wins over factor evidence.  For an
    entry/add review, at least one matching active strategy must have all selected
    factors available and non-adverse, with one or more supportive factors.
    """
    decisions = tuple(discipline_decisions)
    exit_decision = _first(decisions, DisciplineDecisionStatus.EXIT)
    if exit_decision is not None:
        return ManualActionAssessment(
            ManualActionStatus.EXIT_REVIEW,
            exit_decision.matched_level,
            None,
            (),
            (f"个人纪律“{exit_decision.discipline.name}”的清仓价已触及。",),
        )
    take_profit_decision = _first(decisions, DisciplineDecisionStatus.TAKE_PROFIT)
    if take_profit_decision is not None:
        return ManualActionAssessment(
            ManualActionStatus.TAKE_PROFIT_REVIEW,
            take_profit_decision.matched_level,
            None,
            (),
            (f"个人纪律“{take_profit_decision.discipline.name}”的止盈价已触及。",),
        )

    aligned = tuple(
        profile for profile in strategies if _is_factor_aligned(profile, factor_directions)
    )
    add_decision = _first(decisions, DisciplineDecisionStatus.ADD_CONDITION_MET)
    if add_decision is not None:
        return _entry_action(
            ManualActionStatus.CONSIDER_ADD,
            add_decision,
            strategies,
            aligned,
            factor_directions,
        )
    buy_decision = _first(decisions, DisciplineDecisionStatus.BUY_CANDIDATE)
    if buy_decision is not None:
        return _entry_action(
            ManualActionStatus.CONSIDER_ENTRY,
            buy_decision,
            strategies,
            aligned,
            factor_directions,
        )

    next_buy = next(
        (item.discipline for item in decisions if item.status is DisciplineDecisionStatus.OBSERVE),
        None,
    )
    if not strategies:
        reason = "没有匹配当前市场的启用个人策略；仅保留个人纪律价位供复核。"
    elif not aligned:
        reason = _alignment_gap(factor_directions, strategies)
    else:
        reason = "策略因子没有明显冲突，但个人纪律的入场或加仓价尚未触及。"
    if next_buy is not None:
        reason = f"{reason} 等待“{next_buy.name}”买入价 {next_buy.buy_price}。"
        level = next_buy.buy_price
    else:
        level = None
    return ManualActionAssessment(ManualActionStatus.OBSERVE, level, None, (), (reason,))


def _entry_action(
    status: ManualActionStatus,
    decision: DisciplineDecision,
    strategies: Sequence[StrategyProfile],
    aligned: Sequence[StrategyProfile],
    factor_directions: Mapping[str, str],
) -> ManualActionAssessment:
    label = "加仓" if status is ManualActionStatus.CONSIDER_ADD else "建仓"
    if aligned:
        first = aligned[0]
        return ManualActionAssessment(
            status,
            decision.matched_level,
            first.max_position_pct,
            tuple(item.name for item in aligned),
            (
                f"个人纪律“{decision.discipline.name}”的{label}价已触及。",
                f"启用策略“{first.name}”所选因子已可用且无不利方向。",
            ),
        )
    if not strategies:
        gap = "没有匹配当前市场的启用策略，不能将纪律价位升级为行动建议。"
    else:
        gap = _alignment_gap(factor_directions, strategies)
    return ManualActionAssessment(
        ManualActionStatus.OBSERVE,
        decision.matched_level,
        None,
        (),
        (f"个人纪律“{decision.discipline.name}”的{label}价已触及。", gap),
    )


def _is_factor_aligned(profile: StrategyProfile, directions: Mapping[str, str]) -> bool:
    selected = [directions.get(identifier, "unavailable") for identifier in profile.factor_ids]
    return (
        bool(selected)
        and "adverse" not in selected
        and "unavailable" not in selected
        and "supportive" in selected
    )


def _alignment_gap(
    directions: Mapping[str, str], strategies: Sequence[StrategyProfile]
) -> str:
    selected_directions = [
        directions.get(identifier, "unavailable")
        for strategy in strategies
        for identifier in strategy.factor_ids
    ]
    unavailable = sum(value == "unavailable" for value in selected_directions)
    adverse = sum(value == "adverse" for value in selected_directions)
    if unavailable:
        return f"策略因子尚有 {unavailable} 项数据不足，维持观察。"
    if adverse:
        return f"策略因子中有 {adverse} 项不利方向，维持观察。"
    return "策略所选因子缺少支持方向，维持观察。"


def _first(
    decisions: Sequence[DisciplineDecision], status: DisciplineDecisionStatus
) -> DisciplineDecision | None:
    return next((item for item in decisions if item.status is status), None)
