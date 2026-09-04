"""Candidate-pool concepts, deliberately separated from order decisions."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal

from ai_trading_agent.domain.aggregate.market import Instrument


@dataclass(frozen=True, slots=True)
class CandidateObservation:
    """One public quote plus the limited fields suitable for a research screen."""

    instrument: Instrument
    name: str
    last_price: Decimal
    change_percent: Decimal | None
    turnover: Decimal | None
    high_price: Decimal | None
    low_price: Decimal | None
    observed_at: datetime
    source: str

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("candidate name must not be empty")
        if self.last_price < 0:
            raise ValueError("candidate last_price must not be negative")
        if self.turnover is not None and self.turnover < 0:
            raise ValueError("candidate turnover must not be negative")
        if self.high_price is not None and self.high_price < 0:
            raise ValueError("candidate high_price must not be negative")
        if self.low_price is not None and self.low_price < 0:
            raise ValueError("candidate low_price must not be negative")
        if self.observed_at.tzinfo is None:
            raise ValueError("candidate observed_at must be timezone-aware")
        if not self.source.strip():
            raise ValueError("candidate source must not be empty")
        object.__setattr__(self, "name", self.name.strip())
        object.__setattr__(self, "source", self.source.strip().lower())
        object.__setattr__(self, "observed_at", self.observed_at.astimezone(UTC))


@dataclass(frozen=True, slots=True)
class RankedCandidate:
    """A transparent screen result, not a trade signal or an order."""

    observation: CandidateObservation
    score: Decimal
    reasons: tuple[str, ...]

    def __post_init__(self) -> None:
        if not Decimal("0") <= self.score <= Decimal("100"):
            raise ValueError("candidate score must be between 0 and 100")
        if not self.reasons:
            raise ValueError("candidate reasons must not be empty")
