"""Use cases for explainable chart and volume-profile research."""

from __future__ import annotations

from typing import Protocol

from ai_trading_agent.domain.aggregate.market import Instrument
from ai_trading_agent.domain.aggregate.technical import (
    PriceBar,
    TechnicalStudy,
    analyze_technical_study,
)
from ai_trading_agent.domain.enums.technical import BarTimeframe


class HistoricalBarsProvider(Protocol):
    name: str

    async def get_daily_bars(self, instrument: Instrument, limit: int) -> tuple[PriceBar, ...]:
        """Return ascending daily OHLCV bars from one configured provider."""


class AnalyzeTechnicalStudyHandler:
    def __init__(self, provider: HistoricalBarsProvider) -> None:
        self._provider = provider

    async def handle(
        self,
        instrument: Instrument,
        timeframe: BarTimeframe,
        *,
        limit: int = 180,
    ) -> TechnicalStudy:
        if not 60 <= limit <= 1_200:
            raise ValueError("limit must be between 60 and 1200")
        bars = await self._provider.get_daily_bars(instrument, limit)
        return analyze_technical_study(instrument, bars, timeframe, self._provider.name)
