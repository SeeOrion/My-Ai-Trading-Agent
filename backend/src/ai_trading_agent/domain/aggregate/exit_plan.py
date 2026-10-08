"""Persisted, versioned exit plan independent of HTTP and data providers."""

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal


@dataclass(frozen=True, slots=True)
class PositionExitPlan:
    stop_price: Decimal
    target_price: Decimal
    reviewed_at: datetime
    action: str = "hold"
    basis: tuple[str, ...] = ()
    data_notes: tuple[str, ...] = ()
    version: str = "adaptive_v2"

    def __post_init__(self) -> None:
        if min(self.stop_price, self.target_price) <= 0:
            raise ValueError("exit plan prices must be positive")
        if self.reviewed_at.tzinfo is None:
            raise ValueError("exit plan review must be timezone-aware")
