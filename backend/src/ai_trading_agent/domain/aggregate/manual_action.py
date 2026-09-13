"""Auditable manual-action result for one selected instrument."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from ai_trading_agent.domain.enums.research import ManualActionStatus


@dataclass(frozen=True, slots=True)
class ManualActionAssessment:
    """A decision-support state derived from facts and user-authored constraints."""

    status: ManualActionStatus
    price_level: Decimal | None
    max_position_pct: Decimal | None
    strategy_names: tuple[str, ...]
    rationale: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.rationale:
            raise ValueError("manual action needs at least one rationale")
        if self.price_level is not None and self.price_level <= Decimal("0"):
            raise ValueError("price_level must be positive")
