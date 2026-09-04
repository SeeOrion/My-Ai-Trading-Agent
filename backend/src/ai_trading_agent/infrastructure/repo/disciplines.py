"""PostgreSQL repository for versioned personal trading disciplines."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from ai_trading_agent.domain.aggregate.discipline import TradingDiscipline
from ai_trading_agent.infrastructure.repo.models import TradingDisciplineRecord


class SqlAlchemyTradingDisciplineRepository:
    def __init__(self, sessions: async_sessionmaker[AsyncSession]) -> None:
        self._sessions = sessions

    async def list(self) -> list[TradingDiscipline]:
        async with self._sessions() as session:
            statement = select(TradingDisciplineRecord).order_by(
                TradingDisciplineRecord.updated_at.desc()
            )
            records = (await session.scalars(statement)).all()
            return [_to_domain(record) for record in records]

    async def get(self, discipline_id: str) -> TradingDiscipline | None:
        async with self._sessions() as session:
            record = await session.get(TradingDisciplineRecord, discipline_id)
            return None if record is None else _to_domain(record)

    async def save(self, discipline: TradingDiscipline) -> TradingDiscipline:
        async with self._sessions() as session:
            record = await session.get(TradingDisciplineRecord, str(discipline.discipline_id))
            if record is None:
                record = TradingDisciplineRecord(
                    discipline_id=str(discipline.discipline_id),
                    name=discipline.name,
                    symbol=discipline.instrument.symbol,
                    market=discipline.instrument.market.value,
                    status=discipline.status.value,
                    version=discipline.version,
                    definition=discipline.definition(),
                )
                session.add(record)
            else:
                record.name = discipline.name
                record.symbol = discipline.instrument.symbol
                record.market = discipline.instrument.market.value
                record.status = discipline.status.value
                record.version = discipline.version
                record.definition = discipline.definition()
            await session.commit()
            await session.refresh(record)
            return _to_domain(record)


def _to_domain(record: TradingDisciplineRecord) -> TradingDiscipline:
    return TradingDiscipline.from_record(
        discipline_id=record.discipline_id,
        name=record.name,
        symbol=record.symbol,
        market=record.market,
        status=record.status,
        version=record.version,
        definition=record.definition,
    )
