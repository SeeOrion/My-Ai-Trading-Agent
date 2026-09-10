"""Use cases for persisted watchlist research snapshots."""

from __future__ import annotations

from typing import Protocol

from ai_trading_agent.domain.aggregate.watchlist_analysis import WatchlistAnalysisSnapshot


class WatchlistAnalysisRepository(Protocol):
    async def list_latest(self) -> list[WatchlistAnalysisSnapshot]: ...

    async def get_latest(self, watchlist_item_id: str) -> WatchlistAnalysisSnapshot | None: ...

    async def save(self, analysis: WatchlistAnalysisSnapshot) -> WatchlistAnalysisSnapshot: ...


class ListLatestWatchlistAnalysesHandler:
    def __init__(self, repository: WatchlistAnalysisRepository) -> None:
        self._repository = repository

    async def handle(self) -> list[WatchlistAnalysisSnapshot]:
        return await self._repository.list_latest()


class GetLatestWatchlistAnalysisHandler:
    def __init__(self, repository: WatchlistAnalysisRepository) -> None:
        self._repository = repository

    async def handle(self, watchlist_item_id: str) -> WatchlistAnalysisSnapshot | None:
        return await self._repository.get_latest(watchlist_item_id)


class SaveWatchlistAnalysisHandler:
    def __init__(self, repository: WatchlistAnalysisRepository) -> None:
        self._repository = repository

    async def handle(self, analysis: WatchlistAnalysisSnapshot) -> WatchlistAnalysisSnapshot:
        return await self._repository.save(analysis)
