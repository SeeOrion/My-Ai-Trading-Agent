"""Use cases for versioned personal trading disciplines."""

from __future__ import annotations

from typing import Protocol

from ai_trading_agent.domain.aggregate.discipline import TradingDiscipline


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
