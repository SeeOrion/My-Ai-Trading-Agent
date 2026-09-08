"""PostgreSQL persistence for private watchlists and paper positions."""

from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from ai_trading_agent.domain.aggregate.market import Instrument
from ai_trading_agent.domain.aggregate.watchlist import PaperPosition, WatchlistItem
from ai_trading_agent.domain.enums.market import InstrumentType, Market
from ai_trading_agent.infrastructure.repo.models import PaperPositionRecord, WatchlistItemRecord


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
