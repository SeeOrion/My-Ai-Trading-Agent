"""Hard entry gate derived from a user's declared trading disciplines."""

from collections.abc import Sequence

from ai_trading_agent.domain.aggregate.discipline_decision import DisciplineDecision
from ai_trading_agent.domain.enums.research import DisciplineDecisionStatus


def disciplined_entry_blockers(decisions: Sequence[DisciplineDecision]) -> tuple[str, ...]:
    """Allow a new simulated entry only when every applicable plan says buy.

    No matching active plan is deliberately a blocker: autonomous simulation
    must not invent an entry outside the user's explicit price discipline.
    """
    if not decisions:
        return ("未配置该标的的启用个人纪律；严格纪律模式不允许新建模拟仓位。",)
    return tuple(
        f"个人纪律「{item.discipline.name}」当前为{item.status.value}，未满足买入条件，不允许新建模拟仓位。"
        for item in decisions
        if item.status is not DisciplineDecisionStatus.BUY_CANDIDATE
    )
