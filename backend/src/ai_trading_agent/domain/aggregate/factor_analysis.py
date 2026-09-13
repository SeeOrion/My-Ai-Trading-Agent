"""Provider-neutral, point-in-time observations for the built-in factor set."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from ai_trading_agent.domain.aggregate.market import Instrument


@dataclass(frozen=True, slots=True)
class FactorObservation:
    """One factor result; missing inputs are explicitly unavailable, never zero-filled."""

    identifier: str
    name: str
    theme: str
    value: Decimal | None
    unit: str
    direction: str
    interpretation: str
    source: str | None
    unavailable_reason: str | None = None

    def __post_init__(self) -> None:
        if self.direction not in {"supportive", "adverse", "neutral", "unavailable"}:
            raise ValueError("invalid factor direction")
        if self.value is None and self.direction != "unavailable":
            raise ValueError("missing factor values must be unavailable")
        if self.value is not None and self.direction == "unavailable":
            raise ValueError("available factor values need a direction")
        if self.value is None and not self.unavailable_reason:
            raise ValueError("unavailable factors need a reason")


@dataclass(frozen=True, slots=True)
class FactorAnalysis:
    instrument: Instrument
    observed_at: datetime
    observations: tuple[FactorObservation, ...]

    @property
    def available_count(self) -> int:
        return sum(item.value is not None for item in self.observations)

    @property
    def supportive_count(self) -> int:
        return sum(item.direction == "supportive" for item in self.observations)

    @property
    def adverse_count(self) -> int:
        return sum(item.direction == "adverse" for item in self.observations)
