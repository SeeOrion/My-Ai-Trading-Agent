"""Market-data use cases."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from ai_trading_agent.application.ports import MarketDataProvider
from ai_trading_agent.domain.aggregate.market import Instrument, Quote


class MarketDataUnavailableError(RuntimeError):
    """Raised when no configured adapter can answer a market-data query."""


class StaleQuoteError(RuntimeError):
    """Raised when an upstream quote is older than the caller allows."""


@dataclass(frozen=True, slots=True)
class GetLatestQuote:
    """Request the latest quote for an instrument within a freshness budget."""

    instrument: Instrument
    max_age: timedelta = timedelta(minutes=15)

    def __post_init__(self) -> None:
        if self.max_age <= timedelta(0):
            raise ValueError("max_age must be positive")


class GetLatestQuoteHandler:
    """Routes a quote query to the first compatible configured adapter."""

    def __init__(self, providers: list[MarketDataProvider]) -> None:
        self._providers = providers

    async def handle(self, query: GetLatestQuote, *, now: datetime | None = None) -> Quote:
        observed_now = (now or datetime.now(UTC)).astimezone(UTC)
        compatible_providers = [
            provider for provider in self._providers if provider.supports(query.instrument.market)
        ]
        if not compatible_providers:
            raise MarketDataUnavailableError(
                f"no configured provider supports {query.instrument.market.value}"
            )

        errors: list[str] = []
        for provider in compatible_providers:
            try:
                quotes = await provider.get_latest_quotes([query.instrument])
            except Exception as error:  # adapter failures are contained at the boundary
                errors.append(f"{provider.name}: {error}")
                continue
            if len(quotes) != 1 or quotes[0].instrument != query.instrument:
                errors.append(f"{provider.name}: invalid quote response")
                continue
            quote = quotes[0]
            if observed_now - quote.observed_at > query.max_age:
                errors.append(f"{provider.name}: stale quote")
                continue
            return quote

        detail = "; ".join(errors) or "provider returned no quote"
        raise MarketDataUnavailableError(detail)
