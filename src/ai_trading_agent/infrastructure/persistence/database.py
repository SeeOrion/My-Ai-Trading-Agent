"""Database wiring kept outside the domain and application layers."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)


def create_database_engine(database_url: str) -> AsyncEngine:
    """Create an async PostgreSQL engine from an injected URL.

    The caller owns configuration loading so this module never reads local secret files.
    """
    if not database_url.startswith("postgresql+asyncpg://"):
        raise ValueError("database_url must use the postgresql+asyncpg driver")
    return create_async_engine(database_url, pool_pre_ping=True)


def create_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(engine, expire_on_commit=False)


@asynccontextmanager
async def session_scope(
    sessions: async_sessionmaker[AsyncSession],
) -> AsyncIterator[AsyncSession]:
    async with sessions() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
