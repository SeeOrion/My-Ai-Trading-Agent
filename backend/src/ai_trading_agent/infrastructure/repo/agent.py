"""Durable agent evidence and independently versioned account settings."""

from contextlib import asynccontextmanager
from datetime import UTC, datetime
from uuid import uuid4
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from ai_trading_agent.infrastructure.repo.models import AgentAccountRecord, AgentAuditRecord


class AgentRepository:
    def __init__(self, sessions):
        self.sessions = sessions

    async def ensure(self, account):
        async with self.sessions() as session:
            await session.execute(
                insert(AgentAccountRecord)
                .values(portfolio_id=str(account), generation=1, settings={})
                .on_conflict_do_nothing()
            )
            await session.commit()

    async def config(self, account):
        async with self.sessions() as session:
            row = await session.get(AgentAccountRecord, str(account))
            return (row.generation, row.settings) if row else (0, {})

    async def save_config(self, account, settings):
        await self.ensure(account)
        async with self.guard(account) as (session, row):
            row.settings = settings
            row.generation += 1
            return row.generation

    @asynccontextmanager
    async def guard(self, account):
        # Held through application of a result. Disabling waits for an already
        # committing action; after disable returns, an old generation cannot act.
        async with self.sessions() as session:
            async with session.begin():
                row = await session.scalar(
                    select(AgentAccountRecord)
                    .where(AgentAccountRecord.portfolio_id == str(account))
                    .with_for_update()
                )
                yield session, row

    async def audit(self, account, symbol, kind, payload, position_id=None):
        identifier = str(uuid4())
        async with self.sessions() as session:
            session.add(
                AgentAuditRecord(
                    audit_id=identifier,
                    portfolio_id=str(account),
                    position_id=str(position_id) if position_id else None,
                    symbol=symbol,
                    kind=kind,
                    created_at=datetime.now(UTC),
                    payload=payload,
                )
            )
            await session.commit()
        return identifier

    async def finish(self, identifier, outcome, position_id=None):
        async with self.sessions() as session:
            row = await session.get(AgentAuditRecord, identifier)
            row.payload = {
                **row.payload,
                "rule_review": {**row.payload.get("rule_review", {}), **outcome},
            }
            if position_id:
                row.position_id = str(position_id)
            await session.commit()

    async def save_result(self, identifier, payload):
        async with self.sessions() as session:
            row = await session.get(AgentAuditRecord, identifier)
            row.payload = payload
            await session.commit()

    async def history(self, account, position_id=None, limit=50):
        async with self.sessions() as session:
            query = select(AgentAuditRecord).where(AgentAuditRecord.portfolio_id == str(account))
            if position_id:
                query = query.where(
                    AgentAuditRecord.position_id == str(position_id), AgentAuditRecord.kind == "buy"
                )
            rows = (
                await session.scalars(
                    query.order_by(AgentAuditRecord.created_at.desc()).limit(limit)
                )
            ).all()
            return [
                {
                    "audit_id": r.audit_id,
                    "symbol": r.symbol,
                    "kind": r.kind,
                    "position_id": r.position_id,
                    "created_at": r.created_at.isoformat(),
                    **r.payload,
                }
                for r in rows
            ]
