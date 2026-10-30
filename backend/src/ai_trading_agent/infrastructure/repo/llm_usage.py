"""Durable counters, aggregated in SQL instead of loading request history."""

from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import case, func, select

from ai_trading_agent.infrastructure.repo.models import LLMUsageRecord as Row


class SqlAlchemyLLMUsageRepository:
    def __init__(self, sessions):
        self._sessions = sessions

    async def record(self, event: dict) -> None:
        async with self._sessions() as session:
            session.add(Row(event_id=str(uuid4()), created_at=datetime.now(UTC), **event))
            await session.commit()

    async def summary(self, since: datetime) -> dict:
        counters = (
            "input_tokens",
            "output_tokens",
            "total_tokens",
            "cached_tokens",
            "reasoning_tokens",
        )
        query = (
            select(
                Row.feature,
                Row.model,
                Row.status,
                func.count().label("events"),
                func.sum(case((Row.total_tokens.is_(None), 1), else_=0)).label("unknown_usage"),
                *(func.sum(getattr(Row, name)).label(name) for name in counters),
            )
            .where(Row.created_at >= since)
            .group_by(Row.feature, Row.model, Row.status)
        )
        async with self._sessions() as session:
            rows = (await session.execute(query)).mappings().all()
        return {"since": since.isoformat(), "groups": [dict(row) for row in rows]}
