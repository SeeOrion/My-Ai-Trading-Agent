"""PostgreSQL persistence for private watchlists and paper positions."""

from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from ai_trading_agent.domain.aggregate.market import Instrument
from ai_trading_agent.domain.aggregate.watchlist import PaperPosition, WatchlistItem
from ai_trading_agent.domain.aggregate.watchlist_analysis import (
    AnalysisTag,
    WatchlistAnalysisSnapshot,
)
from ai_trading_agent.domain.enums.market import InstrumentType, Market
from ai_trading_agent.domain.enums.research import WatchlistAnalysisStatus
from ai_trading_agent.infrastructure.repo.models import (
    PaperPositionRecord,
    WatchlistAnalysisSnapshotRecord,
    WatchlistItemRecord,
)


class SqlAlchemyWatchlistRepository:
    def __init__(self, sessions: async_sessionmaker[AsyncSession]) -> None:
        self._sessions = sessions

    async def list(self) -> list[WatchlistItem]:
        async with self._sessions() as session:
            return [
                _watch(record)
                for record in (
                    await session.scalars(
                        select(WatchlistItemRecord).order_by(WatchlistItemRecord.updated_at.desc())
                    )
                ).all()
            ]

    async def get(self, item_id: str) -> WatchlistItem | None:
        async with self._sessions() as session:
            record = await session.get(WatchlistItemRecord, item_id)
            return None if record is None else _watch(record)

    async def save(self, item: WatchlistItem) -> WatchlistItem:
        async with self._sessions() as session:
            record = await session.get(WatchlistItemRecord, str(item.item_id))
            if record is None:
                record = WatchlistItemRecord(
                    item_id=str(item.item_id),
                    symbol=item.instrument.symbol,
                    market=item.instrument.market.value,
                    instrument_type=item.instrument.instrument_type.value,
                    label=item.label,
                    notes=item.notes,
                )
                session.add(record)
            else:
                record.symbol, record.market, record.instrument_type, record.label, record.notes = (
                    item.instrument.symbol,
                    item.instrument.market.value,
                    item.instrument.instrument_type.value,
                    item.label,
                    item.notes,
                )
            await session.commit()
            await session.refresh(record)
            return _watch(record)

    async def delete(self, item_id: str) -> bool:
        async with self._sessions() as session:
            record = await session.get(WatchlistItemRecord, item_id)
            if record is None:
                return False
            await session.delete(record)
            await session.commit()
            return True


class SqlAlchemyPaperPositionRepository:
    def __init__(self, sessions: async_sessionmaker[AsyncSession]) -> None:
        self._sessions = sessions

    async def list(self) -> list[PaperPosition]:
        async with self._sessions() as session:
            return [
                _position(record)
                for record in (
                    await session.scalars(
                        select(PaperPositionRecord).order_by(PaperPositionRecord.updated_at.desc())
                    )
                ).all()
            ]

    async def get(self, position_id: str) -> PaperPosition | None:
        async with self._sessions() as session:
            record = await session.get(PaperPositionRecord, position_id)
            return None if record is None else _position(record)

    async def save(self, position: PaperPosition) -> PaperPosition:
        async with self._sessions() as session:
            record = await session.get(PaperPositionRecord, str(position.position_id))
            if record is None:
                record = PaperPositionRecord(
                    position_id=str(position.position_id),
                    symbol=position.instrument.symbol,
                    market=position.instrument.market.value,
                    instrument_type=position.instrument.instrument_type.value,
                    quantity=position.quantity,
                    average_cost=position.average_cost,
                    notes=position.notes,
                )
                session.add(record)
            else:
                record.symbol, record.market, record.instrument_type = (
                    position.instrument.symbol,
                    position.instrument.market.value,
                    position.instrument.instrument_type.value,
                )
                record.quantity, record.average_cost, record.notes = (
                    position.quantity,
                    position.average_cost,
                    position.notes,
                )
            await session.commit()
            await session.refresh(record)
            return _position(record)

    async def delete(self, position_id: str) -> bool:
        async with self._sessions() as session:
            record = await session.get(PaperPositionRecord, position_id)
            if record is None:
                return False
            await session.delete(record)
            await session.commit()
            return True


class SqlAlchemyWatchlistAnalysisRepository:
    def __init__(self, sessions: async_sessionmaker[AsyncSession]) -> None:
        self._sessions = sessions

    async def list_latest(self) -> list[WatchlistAnalysisSnapshot]:
        async with self._sessions() as session:
            records = (
                await session.scalars(
                    select(WatchlistAnalysisSnapshotRecord).order_by(
                        WatchlistAnalysisSnapshotRecord.watchlist_item_id,
                        WatchlistAnalysisSnapshotRecord.observed_at.desc(),
                    )
                )
            ).all()
        seen: set[str] = set()
        latest: list[WatchlistAnalysisSnapshot] = []
        for record in records:
            if record.watchlist_item_id not in seen:
                latest.append(_analysis(record))
                seen.add(record.watchlist_item_id)
        return latest

    async def get_latest(self, watchlist_item_id: str) -> WatchlistAnalysisSnapshot | None:
        async with self._sessions() as session:
            record = await session.scalar(
                select(WatchlistAnalysisSnapshotRecord)
                .where(WatchlistAnalysisSnapshotRecord.watchlist_item_id == watchlist_item_id)
                .order_by(WatchlistAnalysisSnapshotRecord.observed_at.desc())
                .limit(1)
            )
            return None if record is None else _analysis(record)

    async def save(self, analysis: WatchlistAnalysisSnapshot) -> WatchlistAnalysisSnapshot:
        async with self._sessions() as session:
            record = WatchlistAnalysisSnapshotRecord(
                analysis_id=str(analysis.analysis_id),
                watchlist_item_id=str(analysis.watchlist_item_id),
                symbol=analysis.instrument.symbol,
                market=analysis.instrument.market.value,
                instrument_type=analysis.instrument.instrument_type.value,
                observed_at=analysis.observed_at,
                status=analysis.status.value,
                tags=[tag.definition() for tag in analysis.tags],
                ai_summary=analysis.ai_summary,
                notices=list(analysis.notices),
            )
            session.add(record)
            await session.commit()
            await session.refresh(record)
            return _analysis(record)


def _instrument(record: WatchlistItemRecord | PaperPositionRecord) -> Instrument:
    return Instrument(record.symbol, Market(record.market), InstrumentType(record.instrument_type))


def _watch(record: WatchlistItemRecord) -> WatchlistItem:
    return WatchlistItem(UUID(record.item_id), _instrument(record), record.label, record.notes)


def _position(record: PaperPositionRecord) -> PaperPosition:
    return PaperPosition(
        UUID(record.position_id),
        _instrument(record),
        Decimal(str(record.quantity)),
        Decimal(str(record.average_cost)),
        record.notes,
    )


def _analysis(record: WatchlistAnalysisSnapshotRecord) -> WatchlistAnalysisSnapshot:
    return WatchlistAnalysisSnapshot(
        analysis_id=UUID(record.analysis_id),
        watchlist_item_id=UUID(record.watchlist_item_id),
        instrument=Instrument(
            record.symbol,
            Market(record.market),
            InstrumentType(record.instrument_type),
        ),
        observed_at=record.observed_at,
        status=WatchlistAnalysisStatus(record.status),
        tags=tuple(
            AnalysisTag(
                category=str(item["category"]),
                label=str(item["label"]),
                tone=str(item.get("tone", "neutral")),
            )
            for item in record.tags
        ),
        ai_summary=record.ai_summary,
        notices=tuple(str(item) for item in record.notices),
    )
