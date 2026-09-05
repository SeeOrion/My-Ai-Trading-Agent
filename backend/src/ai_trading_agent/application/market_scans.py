"""Application use case for persistable, market-wide research scans."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Protocol
from uuid import uuid4

from ai_trading_agent.domain.aggregate.market_scan import (
    MarketDataRetentionResult,
    MarketScanBatch,
    MarketScanRun,
)
from ai_trading_agent.domain.enums.market import Market


class MarketScanProvider(Protocol):
    name: str

    async def scan_market(self, market: Market) -> MarketScanBatch:
        """Return all usable observations from one documented market universe."""


class MarketScanRepository(Protocol):
    async def save(self, run: MarketScanRun, batch: MarketScanBatch | None = None) -> MarketScanRun:
        """Persist a completed or failed run and optional snapshot rows atomically."""

    async def latest(self, market: Market) -> MarketScanRun | None:
        """Return the most recently started run for a market."""

    async def purge_expired(self, cutoff: datetime) -> MarketDataRetentionResult:
        """Delete market snapshots and run records older than the cutoff."""


class RunMarketScanHandler:
    def __init__(self, provider: MarketScanProvider, repository: MarketScanRepository) -> None:
        self._provider = provider
        self._repository = repository

    async def handle(self, market: Market) -> MarketScanRun:
        started_at = datetime.now(UTC)
        try:
            batch = await self._provider.scan_market(market)
        except Exception as error:
            failed = MarketScanRun(
                run_id=uuid4(),
                market=market,
                source=self._provider.name,
                status="failed",
                started_at=started_at,
                completed_at=datetime.now(UTC),
                universe_size=0,
                snapshot_count=0,
                error_message=str(error),
            )
            return await self._repository.save(failed)
        completed = MarketScanRun(
            run_id=uuid4(),
            market=market,
            source=batch.source,
            status="completed",
            started_at=started_at,
            completed_at=datetime.now(UTC),
            universe_size=batch.universe_size,
            snapshot_count=len(batch.snapshots),
        )
        return await self._repository.save(completed, batch)


class GetLatestMarketScanHandler:
    def __init__(self, repository: MarketScanRepository) -> None:
        self._repository = repository

    async def handle(self, market: Market) -> MarketScanRun | None:
        return await self._repository.latest(market)


class PurgeExpiredMarketDataHandler:
    def __init__(self, repository: MarketScanRepository, retention_days: int = 7) -> None:
        if retention_days != 7:
            raise ValueError("market-data retention must remain seven days")
        self._repository = repository
        self._retention_days = retention_days

    async def handle(self, *, now: datetime | None = None) -> MarketDataRetentionResult:
        observed_now = (now or datetime.now(UTC)).astimezone(UTC)
        cutoff = observed_now - timedelta(days=self._retention_days)
        return await self._repository.purge_expired(cutoff)
