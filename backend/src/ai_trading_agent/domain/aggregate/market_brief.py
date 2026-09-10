"""Provider-neutral observations used by the focused market-close brief."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal


@dataclass(frozen=True, slots=True)
class IndexSnapshot:
    """One named broad-market index snapshot."""

    symbol: str
    name: str
    last_price: Decimal
    price_change: Decimal | None
    change_percent: Decimal | None

    def __post_init__(self) -> None:
        if not self.symbol.strip() or not self.name.strip():
            raise ValueError("index symbol and name must not be empty")
        if self.last_price < 0:
            raise ValueError("index last_price must not be negative")


@dataclass(frozen=True, slots=True)
class SectorPerformance:
    """An industry-index observation ranked by its reported daily move."""

    symbol: str
    name: str
    last_price: Decimal
    change_percent: Decimal

    def __post_init__(self) -> None:
        if not self.symbol.strip() or not self.name.strip():
            raise ValueError("sector symbol and name must not be empty")
        if self.last_price < 0:
            raise ValueError("sector last_price must not be negative")


@dataclass(frozen=True, slots=True)
class PostMarketBrief:
    """A bounded, source-labelled index and sector movement summary."""

    observed_at: datetime
    source: str
    indices: tuple[IndexSnapshot, ...]
    leading_sectors: tuple[SectorPerformance, ...]
    lagging_sectors: tuple[SectorPerformance, ...]

    def __post_init__(self) -> None:
        if self.observed_at.tzinfo is None:
            raise ValueError("observed_at must be timezone-aware")
        if not self.source.strip():
            raise ValueError("source must not be empty")
        if not self.indices:
            raise ValueError("at least one index snapshot is required")
        object.__setattr__(self, "observed_at", self.observed_at.astimezone(UTC))
        object.__setattr__(self, "source", self.source.strip().lower())
