"""Use cases for versioned personal trading disciplines."""

from __future__ import annotations

from typing import Protocol

from ai_trading_agent.domain.aggregate.discipline import TradingDiscipline
from ai_trading_agent.domain.aggregate.discipline_decision import DisciplineDecision
from ai_trading_agent.domain.aggregate.market import Instrument, Quote
from ai_trading_agent.domain.enums.research import DisciplineStatus
from ai_trading_agent.domain.service.discipline_decisions import evaluate_discipline


class TradingDisciplineRepository(Protocol):
    async def list(self) -> list[TradingDiscipline]: ...

    async def get(self, discipline_id: str) -> TradingDiscipline | None: ...

    async def save(self, discipline: TradingDiscipline) -> TradingDiscipline: ...


class ListDisciplinesHandler:
    def __init__(self, repository: TradingDisciplineRepository) -> None:
        self._repository = repository

    async def handle(self) -> list[TradingDiscipline]:
        return await self._repository.list()


class SaveDisciplineHandler:
    def __init__(self, repository: TradingDisciplineRepository) -> None:
        self._repository = repository

    async def handle(self, discipline: TradingDiscipline) -> TradingDiscipline:
        return await self._repository.save(discipline)


class EvaluateInstrumentDisciplinesHandler:
    """Evaluate only active disciplines that exactly match a requested instrument."""

    def __init__(self, repository: TradingDisciplineRepository) -> None:
        self._repository = repository

    async def handle(self, instrument: Instrument, quote: Quote) -> list[DisciplineDecision]:
        if quote.instrument != instrument:
            raise ValueError("instrument and quote must refer to the same instrument")
        disciplines = await self._repository.list()
        return [
            evaluate_discipline(discipline, quote)
            for discipline in disciplines
            if discipline.status is DisciplineStatus.ACTIVE and discipline.instrument == instrument
        ]
