"""A-share quote routing with bounded Futu-to-Tushare degradation."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import dataclass, field
from time import monotonic

from ai_trading_agent.application.ports import MarketDataProvider
from ai_trading_agent.domain.aggregate.market import Instrument, Quote
from ai_trading_agent.domain.enums.market import Market


class QuoteFailoverError(RuntimeError):
    """Raised when neither the primary nor fallback quote source can answer."""


async def get_single_quote(provider: MarketDataProvider, instrument: Instrument) -> Quote:
    """Read exactly one quote while validating an adapter's boundary contract."""
    quotes = await provider.get_latest_quotes([instrument])
    if len(quotes) != 1 or quotes[0].instrument != instrument:
        raise QuoteFailoverError(f"{provider.name}: invalid quote response")
    return quotes[0]


@dataclass(slots=True)
class AShareQuoteFailover:
    """Prefer Futu, then temporarily bypass it after a failed A-share request."""

    primary: MarketDataProvider
    fallback: MarketDataProvider
    secondary_fallbacks: tuple[MarketDataProvider, ...] = ()
    primary_timeout_seconds: float = 5.0
    cooldown_seconds: float = 60.0
    clock: Callable[[], float] = monotonic
    _primary_disabled_until: float = field(default=0.0, init=False)
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock, init=False)

    def __post_init__(self) -> None:
        if self.primary_timeout_seconds <= 0:
            raise ValueError("primary_timeout_seconds must be positive")
        if self.cooldown_seconds <= 0:
            raise ValueError("cooldown_seconds must be positive")

    async def get_latest_quote(self, instrument: Instrument) -> Quote:
        if instrument.market is not Market.A_SHARE:
            raise ValueError("A-share failover only supports A-share instruments")

        errors: list[str] = []
        if await self._primary_is_available():
            try:
                quote = await asyncio.wait_for(
                    get_single_quote(self.primary, instrument),
                    timeout=self.primary_timeout_seconds,
                )
            except Exception as error:
                await self._disable_primary()
                errors.append(f"{self.primary.name}: {error}")
            else:
                return quote
        else:
            errors.append(f"{self.primary.name}: skipped during cooldown")

        for provider in (self.fallback, *self.secondary_fallbacks):
            try:
                return await get_single_quote(provider, instrument)
            except Exception as error:
                errors.append(f"{provider.name}: {error}")
        raise QuoteFailoverError("; ".join(errors))

    async def _primary_is_available(self) -> bool:
        async with self._lock:
            return self.clock() >= self._primary_disabled_until

    async def _disable_primary(self) -> None:
        async with self._lock:
            self._primary_disabled_until = self.clock() + self.cooldown_seconds
