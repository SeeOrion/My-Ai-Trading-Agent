"""A verified display identity for one user-selected instrument."""

from __future__ import annotations

from dataclasses import dataclass

from ai_trading_agent.domain.aggregate.market import Instrument


@dataclass(frozen=True, slots=True)
class InstrumentIdentity:
    instrument: Instrument
    display_name: str
    source: str

    def __post_init__(self) -> None:
        if not self.display_name.strip():
            raise ValueError("display_name must not be empty")
        if not self.source.strip():
            raise ValueError("source must not be empty")
        object.__setattr__(self, "display_name", self.display_name.strip())
        object.__setattr__(self, "source", self.source.strip().lower())
