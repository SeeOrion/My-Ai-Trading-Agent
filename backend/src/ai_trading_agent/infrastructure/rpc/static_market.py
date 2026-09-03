"""In-memory market-data adapter used by local development and tests only."""

from __future__ import annotations

from collections.abc import Iterable

from ai_trading_agent.domain.aggregate.market import Instrument, Quote
from ai_trading_agent.domain.enums.market import Market


class StaticMarketDataProvider:
    """Deterministic adapter; intentionally never fetches remote market data."""

    name = "static"

    def __init__(self, quotes: Iterable[Quote]) -> None:
        self._quotes = {quote.instrument: quote for quote in quotes}

    def supports(self, market: Market) -> bool:
        return any(instrument.market == market for instrument in self._quotes)

    async def get_latest_quotes(self, instruments: Iterable[Instrument]) -> list[Quote]:
        requested = list(instruments)
        missing = [instrument.symbol for instrument in requested if instrument not in self._quotes]
        if missing:
            raise LookupError(f"no static quote for: {', '.join(missing)}")
        return [self._quotes[instrument] for instrument in requested]
