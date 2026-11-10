"""Pure scoring and evidence policies for simulated research agents."""

from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal


@dataclass(frozen=True)
class ResearchPolicy:
    workflow_weight: Decimal = Decimal("0.6")
    research_weight: Decimal = Decimal("0.4")
    entry_threshold: Decimal = Decimal("70")
    validity_seconds: int = 300
    max_price_move: Decimal = Decimal("0.02")

    def __post_init__(self):
        values = (
            self.workflow_weight,
            self.research_weight,
            self.entry_threshold,
            self.max_price_move,
        )
        if not all(value.is_finite() for value in values):
            raise ValueError("policy values must be finite")
        if (
            min(self.workflow_weight, self.research_weight) < 0
            or self.workflow_weight + self.research_weight != 1
        ):
            raise ValueError("weights must be nonnegative and sum to one")
        if (
            not 0 <= self.entry_threshold <= 100
            or self.validity_seconds <= 0
            or not 0 <= self.max_price_move <= 1
        ):
            raise ValueError("invalid research policy")

    def combined_score(self, workflow: Decimal, research: Decimal) -> Decimal:
        if not all(value.is_finite() and 0 <= value <= 100 for value in (workflow, research)):
            raise ValueError("scores must be finite and on a 0..100 scale")
        return self.workflow_weight * workflow + self.research_weight * research

    def quote_blockers(
        self,
        *,
        reference: Decimal,
        current: Decimal,
        researched_at: datetime,
        quoted_at: datetime,
        now: datetime,
    ) -> tuple[str, ...]:
        if any(value.tzinfo is None for value in (researched_at, quoted_at, now)):
            raise ValueError("timestamps must be timezone aware")
        if not all(value.is_finite() and value > 0 for value in (reference, current)):
            return ("报价无效",)
        reasons = []
        ttl = timedelta(seconds=self.validity_seconds)
        if not timedelta(0) <= now - researched_at <= ttl:
            reasons.append("研究已超出有效期")
        if not timedelta(0) <= now - quoted_at <= ttl:
            reasons.append("报价已过期或时间异常")
        if abs(current / reference - 1) > self.max_price_move:
            reasons.append("研究完成后价格超出允许范围")
        return tuple(reasons)


def review_entry(
    policy: ResearchPolicy,
    *,
    status: str,
    workflow_score: Decimal,
    research_score: Decimal | None,
    hard_blockers: tuple[str, ...],
    evidence_risk_blockers: tuple[str, ...] = (),
) -> tuple[Decimal | None, tuple[str, ...]]:
    """Research failure is unavailable, never a fabricated zero or adverse score."""
    blockers = (*hard_blockers, *evidence_risk_blockers)
    if status != "completed" or research_score is None:
        return None, (*blockers, f"买入研究未完成（{status}），暂缓新建仓")
    score = policy.combined_score(workflow_score, research_score)
    if score < policy.entry_threshold:
        blockers = (*blockers, "综合评分未达到买入门槛")
    return score, blockers


def position_advice_eligible(status: str, report: dict) -> bool:
    if status != "completed" or not any(
        r.get("severity") in {"major", "critical"} for r in report.get("risks", [])
    ):
        return False
    return (report.get("recommendation"), report.get("thesis_state")) in {
        ("reduce", "weakened"),
        ("exit", "invalidated"),
    }
