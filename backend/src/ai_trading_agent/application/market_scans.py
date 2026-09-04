"""Application use case for persistable, market-wide research scans."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Protocol
from uuid import uuid4

from ai_trading_agent.domain.aggregate.market_scan import MarketScanBatch, MarketScanRun
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
