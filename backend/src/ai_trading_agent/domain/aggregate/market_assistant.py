"""Bounded, source-attributed output for dashboard market questions."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from ai_trading_agent.domain.aggregate.instrument_identity import CatalogInstrument


@dataclass(frozen=True, slots=True)
class MarketAssistantAnswer:
    """A readable answer plus the evidence categories that informed it."""

    answer: str
    generated_at: datetime
    sources: tuple[str, ...]
    notices: tuple[str, ...]
    candidates: tuple[CatalogInstrument, ...] = ()

    def __post_init__(self) -> None:
        if not self.answer.strip():
            raise ValueError("market assistant answer must not be empty")
        if self.generated_at.tzinfo is None:
            raise ValueError("generated_at must be timezone-aware")
        object.__setattr__(self, "answer", self.answer.strip())
        object.__setattr__(self, "generated_at", self.generated_at.astimezone(UTC))
        object.__setattr__(self, "sources", tuple(_unique_text(self.sources)))
        object.__setattr__(self, "notices", tuple(_unique_text(self.notices)))


def _unique_text(values: tuple[str, ...]) -> list[str]:
    return list(dict.fromkeys(value.strip() for value in values if value.strip()))
