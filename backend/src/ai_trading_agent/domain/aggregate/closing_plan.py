"""Review-only closing-session plans for personally selected instruments."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from ai_trading_agent.domain.aggregate.market import Instrument


@dataclass(frozen=True, slots=True)
class ClosingPlanItem:
    """One auditable preparation item; never an order or broker instruction."""

    watchlist_item_id: UUID
    instrument: Instrument
    label: str
    action: str
    action_label: str
    closing_window: bool
    window_label: str
    next_session_plan: str
    reasons: tuple[str, ...]
    observed_at: datetime | None
    status: str

    def __post_init__(self) -> None:
        if self.action not in {
            "observe",
            "consider_entry",
            "consider_add",
            "take_profit_review",
            "exit_review",
            "data_pending",
        }:
            raise ValueError("unsupported closing-plan action")
        if not self.label.strip() or not self.window_label.strip():
            raise ValueError("closing-plan labels must not be empty")
        if len(self.reasons) > 4:
            raise ValueError("a closing plan supports at most four reasons")
        if self.observed_at is not None:
            if self.observed_at.tzinfo is None:
                raise ValueError("closing-plan observation must be timezone-aware")
            object.__setattr__(self, "observed_at", self.observed_at.astimezone(UTC))


@dataclass(frozen=True, slots=True)
class ClosingPlan:
    """A time-bounded, next-session review plan for the personal watchlist."""

    generated_at: datetime
    items: tuple[ClosingPlanItem, ...]
    notices: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.generated_at.tzinfo is None:
            raise ValueError("closing plan timestamp must be timezone-aware")
        if len(self.notices) > 16:
            raise ValueError("closing plan supports at most sixteen notices")
        object.__setattr__(self, "generated_at", self.generated_at.astimezone(UTC))
