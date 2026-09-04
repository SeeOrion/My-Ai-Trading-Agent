"""Interface helpers for personal trading-discipline persistence."""

from __future__ import annotations

from uuid import UUID

from fastapi import FastAPI

from ai_trading_agent.domain.aggregate.discipline import TradingDiscipline
from ai_trading_agent.domain.aggregate.market import Instrument
from ai_trading_agent.infrastructure.repo.disciplines import SqlAlchemyTradingDisciplineRepository
from ai_trading_agent.interfaces.facade.persistence import private_session_factory
from ai_trading_agent.interfaces.model.http import DisciplineInput


def discipline_repository(app: FastAPI) -> SqlAlchemyTradingDisciplineRepository:
    return SqlAlchemyTradingDisciplineRepository(private_session_factory(app))


async def get_discipline(app: FastAPI, discipline_id: UUID) -> TradingDiscipline | None:
    return await discipline_repository(app).get(str(discipline_id))


def discipline_from_input(
    payload: DisciplineInput,
    discipline_id: UUID,
    version: int,
) -> TradingDiscipline:
    return TradingDiscipline(
        discipline_id=discipline_id,
        name=payload.name,
        instrument=Instrument(payload.symbol, payload.market, payload.instrument_type),
        buy_price=payload.buy_price,
        add_price=payload.add_price,
        take_profit_price=payload.take_profit_price,
        exit_price=payload.exit_price,
        notes=payload.notes,
        status=payload.status,
        version=version,
    )
