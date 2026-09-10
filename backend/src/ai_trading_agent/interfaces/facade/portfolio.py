"""Composition helpers for private watchlist and paper-position features."""

from __future__ import annotations

from uuid import UUID

from fastapi import FastAPI

from ai_trading_agent.domain.aggregate.market import Instrument
from ai_trading_agent.domain.aggregate.watchlist import PaperPosition, WatchlistItem
from ai_trading_agent.infrastructure.repo.portfolio import (
    SqlAlchemyPaperPositionRepository,
    SqlAlchemyWatchlistAnalysisRepository,
    SqlAlchemyWatchlistRepository,
)
from ai_trading_agent.interfaces.facade.persistence import private_session_factory
from ai_trading_agent.interfaces.model.http import PaperPositionInput, WatchlistInput


def watchlist_repository(app: FastAPI) -> SqlAlchemyWatchlistRepository:
    return SqlAlchemyWatchlistRepository(private_session_factory(app))


def paper_position_repository(app: FastAPI) -> SqlAlchemyPaperPositionRepository:
    return SqlAlchemyPaperPositionRepository(private_session_factory(app))


def watchlist_analysis_repository(app: FastAPI) -> SqlAlchemyWatchlistAnalysisRepository:
    return SqlAlchemyWatchlistAnalysisRepository(private_session_factory(app))


async def get_watchlist_item(app: FastAPI, item_id: UUID) -> WatchlistItem | None:
    return await watchlist_repository(app).get(str(item_id))


def watchlist_from_input(payload: WatchlistInput, item_id: UUID) -> WatchlistItem:
    return WatchlistItem(
        item_id,
        Instrument(payload.symbol, payload.market, payload.instrument_type),
        payload.label,
        payload.notes,
    )


def paper_position_from_input(payload: PaperPositionInput, position_id: UUID) -> PaperPosition:
    return PaperPosition(
        position_id,
        Instrument(payload.symbol, payload.market, payload.instrument_type),
        payload.quantity,
        payload.average_cost,
        payload.notes,
    )
