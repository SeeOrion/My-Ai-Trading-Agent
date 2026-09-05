from datetime import UTC, datetime
from decimal import Decimal

import pytest

from ai_trading_agent.application.market_scans import (
    PurgeExpiredMarketDataHandler,
    RunMarketScanHandler,
)
from ai_trading_agent.domain.aggregate.market import Instrument
from ai_trading_agent.domain.aggregate.market_scan import (
    MarketDataRetentionResult,
    MarketScanBatch,
    MarketScanRun,
    MarketSnapshot,
)
from ai_trading_agent.domain.enums.market import Market


class ScanProvider:
    name = "fake_scan"

    def __init__(self, *, fails: bool = False) -> None:
        self.fails = fails

    async def scan_market(self, market: Market) -> MarketScanBatch:
        if self.fails:
            raise RuntimeError("upstream unavailable")
        snapshot = MarketSnapshot(
            instrument=Instrument("600519.SH", market),
            name="Test security",
            observed_at=datetime(2026, 9, 4, tzinfo=UTC),
            source=self.name,
            last_price=Decimal("10"),
        )
        return MarketScanBatch(market, self.name, 2, (snapshot,))


class ScanRepository:
    def __init__(self) -> None:
        self.saved: list[tuple[MarketScanRun, MarketScanBatch | None]] = []

    async def save(
        self, run: MarketScanRun, batch: MarketScanBatch | None = None
    ) -> MarketScanRun:
        self.saved.append((run, batch))
        return run

    async def latest(self, market: Market) -> MarketScanRun | None:
        return None

    async def purge_expired(self, cutoff: datetime) -> MarketDataRetentionResult:
        self.cutoff = cutoff
        return MarketDataRetentionResult(cutoff, 12, 3)


@pytest.mark.asyncio
async def test_market_scan_persists_completed_batch() -> None:
    repository = ScanRepository()

    run = await RunMarketScanHandler(ScanProvider(), repository).handle(Market.A_SHARE)

    assert run.status == "completed"
    assert run.universe_size == 2
    assert repository.saved[0][1] is not None


@pytest.mark.asyncio
async def test_market_scan_persists_failed_run_without_snapshots() -> None:
    repository = ScanRepository()

    run = await RunMarketScanHandler(ScanProvider(fails=True), repository).handle(Market.A_SHARE)

    assert run.status == "failed"
    assert "upstream unavailable" in (run.error_message or "")
    assert repository.saved[0][1] is None


@pytest.mark.asyncio
async def test_market_data_retention_deletes_only_records_older_than_seven_days() -> None:
    repository = ScanRepository()
    now = datetime(2026, 9, 5, 12, 0, tzinfo=UTC)

    result = await PurgeExpiredMarketDataHandler(repository).handle(now=now)

    assert repository.cutoff == datetime(2026, 8, 29, 12, 0, tzinfo=UTC)
    assert result.deleted_snapshot_count == 12
    assert result.deleted_run_count == 3
