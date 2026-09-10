"""Use case for retrieving a selected instrument's financial detail."""

from __future__ import annotations

from typing import Protocol

from ai_trading_agent.domain.aggregate.market import Instrument
from ai_trading_agent.domain.aggregate.watchlist_detail import WatchlistFinancialDetail


class WatchlistFinancialDetailProvider(Protocol):
    """Port for one selected instrument's published financial details."""

    async def get_watchlist_financial_detail(
        self, instrument: Instrument
    ) -> WatchlistFinancialDetail: ...


class GetWatchlistFinancialDetailHandler:
    def __init__(self, provider: WatchlistFinancialDetailProvider) -> None:
        self._provider = provider

    async def handle(self, instrument: Instrument) -> WatchlistFinancialDetail:
        return await self._provider.get_watchlist_financial_detail(instrument)
