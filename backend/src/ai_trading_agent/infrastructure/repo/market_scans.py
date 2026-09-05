"""PostgreSQL repository for auditable market-scan runs and snapshot rows."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from ai_trading_agent.domain.aggregate.market_scan import (
    MarketDataRetentionResult,
    MarketScanBatch,
    MarketScanRun,
)
from ai_trading_agent.domain.enums.market import Market
from ai_trading_agent.infrastructure.repo.models import MarketScanRunRecord, MarketSnapshotRecord


class SqlAlchemyMarketScanRepository:
    def __init__(self, sessions: async_sessionmaker[AsyncSession]) -> None:
        self._sessions = sessions

    async def save(
        self,
        run: MarketScanRun,
        batch: MarketScanBatch | None = None,
    ) -> MarketScanRun:
        if batch is not None and batch.market is not run.market:
            raise ValueError("scan batch market must match scan run market")
        async with self._sessions() as session:
            record = MarketScanRunRecord(
                run_id=str(run.run_id),
                market=run.market.value,
                source=run.source,
                status=run.status,
                started_at=run.started_at,
                completed_at=run.completed_at,
                universe_size=run.universe_size,
                snapshot_count=run.snapshot_count,
                error_message=run.error_message,
            )
            session.add(record)
            if batch is not None:
                session.add_all(
                    [
                        MarketSnapshotRecord(
                            run_id=str(run.run_id),
                            market=snapshot.instrument.market.value,
                            symbol=snapshot.instrument.symbol,
                            name=snapshot.name,
                            currency=snapshot.instrument.currency,
                            observed_at=snapshot.observed_at,
                            source=snapshot.source,
                            last_price=snapshot.last_price,
                            previous_close=snapshot.previous_close,
                            open_price=snapshot.open_price,
                            high_price=snapshot.high_price,
                            low_price=snapshot.low_price,
                            volume=snapshot.volume,
                            turnover=snapshot.turnover,
                            change_percent=snapshot.change_percent,
                            price_to_earnings=snapshot.price_to_earnings,
                            price_to_book=snapshot.price_to_book,
                        )
                        for snapshot in batch.snapshots
                    ]
                )
            await session.commit()
            return run

    async def latest(self, market: Market) -> MarketScanRun | None:
        async with self._sessions() as session:
            statement = (
                select(MarketScanRunRecord)
                .where(MarketScanRunRecord.market == market.value)
                .order_by(MarketScanRunRecord.started_at.desc())
                .limit(1)
            )
            record = (await session.scalars(statement)).first()
            return None if record is None else _to_domain(record)

    async def purge_expired(self, cutoff: datetime) -> MarketDataRetentionResult:
        """Purge expired facts first, then their now-unneeded audit run records."""
        async with self._sessions() as session:
            deleted_snapshots = await session.execute(
                delete(MarketSnapshotRecord).where(MarketSnapshotRecord.observed_at < cutoff)
            )
            deleted_runs = await session.execute(
                delete(MarketScanRunRecord).where(MarketScanRunRecord.completed_at < cutoff)
            )
            await session.commit()
            return MarketDataRetentionResult(
                cutoff=cutoff,
                deleted_snapshot_count=deleted_snapshots.rowcount or 0,
                deleted_run_count=deleted_runs.rowcount or 0,
            )


def _to_domain(record: MarketScanRunRecord) -> MarketScanRun:
    from uuid import UUID

    return MarketScanRun(
        run_id=UUID(record.run_id),
        market=Market(record.market),
        source=record.source,
        status=record.status,
        started_at=record.started_at,
        completed_at=record.completed_at,
        universe_size=record.universe_size,
        snapshot_count=record.snapshot_count,
        error_message=record.error_message,
    )
