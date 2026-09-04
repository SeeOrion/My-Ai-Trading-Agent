from datetime import UTC, datetime
from decimal import Decimal

import pytest

from ai_trading_agent.application.market_scans import RunMarketScanHandler
from ai_trading_agent.domain.aggregate.market import Instrument
from ai_trading_agent.domain.aggregate.market_scan import (
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
