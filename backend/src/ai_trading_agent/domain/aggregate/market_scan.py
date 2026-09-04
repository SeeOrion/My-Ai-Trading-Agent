"""Immutable records for auditable market-wide research scans."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

from ai_trading_agent.domain.aggregate.market import Instrument
from ai_trading_agent.domain.enums.market import Market


@dataclass(frozen=True, slots=True)
class MarketSnapshot:
    """One normalized security observation captured by a market scan."""

    instrument: Instrument
    name: str
    observed_at: datetime
    source: str
    last_price: Decimal
    previous_close: Decimal | None = None
    open_price: Decimal | None = None
    high_price: Decimal | None = None
    low_price: Decimal | None = None
    volume: Decimal | None = None
    turnover: Decimal | None = None
    change_percent: Decimal | None = None
    price_to_earnings: Decimal | None = None
    price_to_book: Decimal | None = None

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("snapshot name must not be empty")
        if not self.source.strip():
            raise ValueError("snapshot source must not be empty")
        if self.observed_at.tzinfo is None:
            raise ValueError("snapshot observed_at must be timezone-aware")
        if self.last_price < 0:
            raise ValueError("snapshot last_price must not be negative")
        for field in (
            "previous_close",
            "open_price",
            "high_price",
            "low_price",
            "volume",
            "turnover",
        ):
            value = getattr(self, field)
            if value is not None and value < 0:
                raise ValueError(f"snapshot {field} must not be negative")
        object.__setattr__(self, "name", self.name.strip())
        object.__setattr__(self, "source", self.source.strip().lower())
        object.__setattr__(self, "observed_at", self.observed_at.astimezone(UTC))


@dataclass(frozen=True, slots=True)
class MarketScanBatch:
    """A provider response before persistence and run-status bookkeeping."""

    market: Market
    source: str
    universe_size: int
    snapshots: tuple[MarketSnapshot, ...]

    def __post_init__(self) -> None:
        if not self.source.strip():
            raise ValueError("scan batch source must not be empty")
        if self.universe_size < 0:
            raise ValueError("scan batch universe_size must not be negative")
        if any(snapshot.instrument.market is not self.market for snapshot in self.snapshots):
            raise ValueError("all scan snapshots must belong to the scan market")
        object.__setattr__(self, "source", self.source.strip().lower())


@dataclass(frozen=True, slots=True)
class MarketScanRun:
    """Persisted outcome of one manual or scheduled full-market scan."""

    run_id: UUID
    market: Market
    source: str
    status: str
    started_at: datetime
    completed_at: datetime
    universe_size: int
    snapshot_count: int
    error_message: str | None = None

    def __post_init__(self) -> None:
        if self.status not in {"completed", "failed"}:
            raise ValueError("scan status must be completed or failed")
        if not self.source.strip():
            raise ValueError("scan source must not be empty")
        if self.started_at.tzinfo is None or self.completed_at.tzinfo is None:
            raise ValueError("scan timestamps must be timezone-aware")
        if self.completed_at < self.started_at:
            raise ValueError("scan completion must not precede start")
        if self.universe_size < 0 or self.snapshot_count < 0:
            raise ValueError("scan counts must not be negative")
        if self.snapshot_count > self.universe_size:
            raise ValueError("snapshot_count must not exceed universe_size")
        if self.status == "failed" and not (self.error_message or "").strip():
            raise ValueError("failed scans must include an error message")
        object.__setattr__(self, "source", self.source.strip().lower())
        object.__setattr__(self, "started_at", self.started_at.astimezone(UTC))
        object.__setattr__(self, "completed_at", self.completed_at.astimezone(UTC))
        if self.error_message is not None:
            object.__setattr__(self, "error_message", self.error_message.strip() or None)
