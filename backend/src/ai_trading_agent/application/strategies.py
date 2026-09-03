"""Use cases for versioned, declarative personal strategy profiles."""

from __future__ import annotations

from typing import Protocol

from ai_trading_agent.domain.strategy import StrategyProfile


class StrategyProfileRepository(Protocol):
    async def list(self) -> list[StrategyProfile]: ...

    async def get(self, strategy_id: str) -> StrategyProfile | None: ...

    async def save(self, profile: StrategyProfile) -> StrategyProfile: ...


class ListStrategiesHandler:
    def __init__(self, repository: StrategyProfileRepository) -> None:
        self._repository = repository

    async def handle(self) -> list[StrategyProfile]:
        return await self._repository.list()


class SaveStrategyHandler:
    def __init__(self, repository: StrategyProfileRepository) -> None:
        self._repository = repository

    async def handle(self, profile: StrategyProfile) -> StrategyProfile:
        return await self._repository.save(profile)
