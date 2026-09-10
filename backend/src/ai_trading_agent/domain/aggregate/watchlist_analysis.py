"""Cached, review-only research summaries for personally selected instruments."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from ai_trading_agent.domain.aggregate.market import Instrument
from ai_trading_agent.domain.enums.research import WatchlistAnalysisStatus


@dataclass(frozen=True, slots=True)
class AnalysisTag:
    """A compact, source-grounded label for a selected instrument."""

    category: str
    label: str
    tone: str = "neutral"

    def __post_init__(self) -> None:
        if not self.category.strip() or len(self.category) > 64:
            raise ValueError("tag category must contain 1 to 64 characters")
        if not self.label.strip() or len(self.label) > 160:
            raise ValueError("tag label must contain 1 to 160 characters")
        if self.tone not in {"positive", "negative", "neutral", "info"}:
            raise ValueError("tag tone is unsupported")

    def definition(self) -> dict[str, str]:
        return {"category": self.category, "label": self.label, "tone": self.tone}


@dataclass(frozen=True, slots=True)
class WatchlistAnalysisSnapshot:
    """A bounded saved result; it never represents a broker instruction."""

    analysis_id: UUID
    watchlist_item_id: UUID
    instrument: Instrument
    observed_at: datetime
    status: WatchlistAnalysisStatus
    tags: tuple[AnalysisTag, ...]
    ai_summary: str | None
    notices: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.observed_at.tzinfo is None:
            raise ValueError("observed_at must be timezone-aware")
        if len(self.tags) > 16:
            raise ValueError("a watchlist analysis supports at most 16 tags")
        if self.ai_summary is not None and len(self.ai_summary) > 2_000:
            raise ValueError("ai_summary must contain at most 2000 characters")
        if len(self.notices) > 32 or any(len(item) > 500 for item in self.notices):
            raise ValueError("analysis notices exceed the allowed size")
        object.__setattr__(self, "observed_at", self.observed_at.astimezone(UTC))
