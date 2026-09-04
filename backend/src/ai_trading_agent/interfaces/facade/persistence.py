"""Shared private-database wiring for interface facades."""

from __future__ import annotations

import os

from fastapi import FastAPI
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from ai_trading_agent.infrastructure.repo.database import (
    create_database_engine,
    create_session_factory,
)
from ai_trading_agent.interfaces.adapter.environment import load_runtime_environment


def private_session_factory(app: FastAPI) -> async_sessionmaker[AsyncSession]:
    sessions = getattr(app.state, "private_sessions", None)
    if sessions is not None:
        return sessions
    load_runtime_environment()
    database_url = os.environ.get("DATABASE_URL", "").strip()
    if not database_url:
        raise RuntimeError("DATABASE_URL is required to save private research preferences")
    app.state.database_engine = create_database_engine(database_url)
    sessions = create_session_factory(app.state.database_engine)
    app.state.private_sessions = sessions
    return sessions
