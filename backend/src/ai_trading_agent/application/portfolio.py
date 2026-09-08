"""Use cases for private watchlists and manually entered paper positions."""

from __future__ import annotations

from typing import Protocol

from ai_trading_agent.domain.aggregate.watchlist import PaperPosition, WatchlistItem


class WatchlistRepository(Protocol):
    async def list(self) -> list[WatchlistItem]: ...
    async def get(self, item_id: str) -> WatchlistItem | None: ...
    async def save(self, item: WatchlistItem) -> WatchlistItem: ...
    async def delete(self, item_id: str) -> bool: ...


class PaperPositionRepository(Protocol):
    async def list(self) -> list[PaperPosition]: ...
    async def get(self, position_id: str) -> PaperPosition | None: ...
    async def save(self, position: PaperPosition) -> PaperPosition: ...
    async def delete(self, position_id: str) -> bool: ...


class ListWatchlistHandler:
    def __init__(self, repository: WatchlistRepository) -> None:
        self._repository = repository

    async def handle(self) -> list[WatchlistItem]:
        return await self._repository.list()


class SaveWatchlistHandler:
    def __init__(self, repository: WatchlistRepository) -> None:
        self._repository = repository

    async def handle(self, item: WatchlistItem) -> WatchlistItem:
        return await self._repository.save(item)


class ListPaperPositionsHandler:
    def __init__(self, repository: PaperPositionRepository) -> None:
        self._repository = repository

    async def handle(self) -> list[PaperPosition]:
        return await self._repository.list()


class SavePaperPositionHandler:
    def __init__(self, repository: PaperPositionRepository) -> None:
        self._repository = repository

    async def handle(self, position: PaperPosition) -> PaperPosition:
        return await self._repository.save(position)
