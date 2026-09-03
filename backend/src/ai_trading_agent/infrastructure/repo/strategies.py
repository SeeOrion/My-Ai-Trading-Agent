"""PostgreSQL repository for declarative personal strategy profiles."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from ai_trading_agent.domain.aggregate.strategy import StrategyProfile
from ai_trading_agent.infrastructure.repo.models import StrategyProfileRecord


class SqlAlchemyStrategyProfileRepository:
    def __init__(self, sessions: async_sessionmaker[AsyncSession]) -> None:
        self._sessions = sessions

    async def list(self) -> list[StrategyProfile]:
        async with self._sessions() as session:
            statement = select(StrategyProfileRecord).order_by(
                StrategyProfileRecord.updated_at.desc()
            )
            records = (await session.scalars(statement)).all()
            return [_to_domain(record) for record in records]

    async def get(self, strategy_id: str) -> StrategyProfile | None:
        async with self._sessions() as session:
            record = await session.get(StrategyProfileRecord, strategy_id)
            return None if record is None else _to_domain(record)

    async def save(self, profile: StrategyProfile) -> StrategyProfile:
        async with self._sessions() as session:
            record = await session.get(StrategyProfileRecord, str(profile.strategy_id))
            if record is None:
                record = StrategyProfileRecord(
                    strategy_id=str(profile.strategy_id),
                    name=profile.name,
                    status=profile.status,
                    version=profile.version,
                    definition=profile.definition(),
                )
                session.add(record)
            else:
                record.name = profile.name
                record.status = profile.status
                record.version = profile.version
                record.definition = profile.definition()
            await session.commit()
            await session.refresh(record)
            return _to_domain(record)


def _to_domain(record: StrategyProfileRecord) -> StrategyProfile:
    return StrategyProfile.from_record(
        strategy_id=record.strategy_id,
        name=record.name,
        status=record.status,
        version=record.version,
        definition=record.definition,
    )
