"""Outbound ports owned by application use cases, not their adapters."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Protocol

from ai_trading_agent.domain.aggregate.market import Instrument, Quote
from ai_trading_agent.domain.enums.market import Market


class MarketDataProvider(Protocol):
    """A source capable of serving current provider-neutral market quotes."""

    name: str

    def supports(self, market: Market) -> bool:
        """Return whether this provider is configured for ``market``."""

    async def get_latest_quotes(self, instruments: Iterable[Instrument]) -> list[Quote]:
        """Return the freshest available quote for every requested instrument."""


class Clock(Protocol):
    """Time source that makes freshness policies deterministic in tests."""

    def now(self):  # type: ignore[no-untyped-def]
        """Return a timezone-aware UTC datetime."""
