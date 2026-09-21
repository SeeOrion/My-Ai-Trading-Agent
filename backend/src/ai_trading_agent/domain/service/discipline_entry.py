"""Hard entry gate derived from a user's declared trading disciplines."""

from collections.abc import Sequence

from ai_trading_agent.domain.aggregate.discipline_decision import DisciplineDecision
from ai_trading_agent.domain.enums.research import DisciplineDecisionStatus


def disciplined_entry_blockers(decisions: Sequence[DisciplineDecision]) -> tuple[str, ...]:
    """Apply declared disciplines as hard constraints only when they exist."""
    if not decisions:
        return ()
    return tuple(
        f"个人纪律「{item.discipline.name}」当前为{item.status.value}，未满足买入条件，不允许新建模拟仓位。"
        for item in decisions
        if item.status is not DisciplineDecisionStatus.BUY_CANDIDATE
    )
