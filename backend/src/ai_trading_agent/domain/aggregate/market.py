"""Market-data bounded context: provider-neutral financial concepts."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal

from ai_trading_agent.domain.enums.market import InstrumentType, Market


@dataclass(frozen=True, slots=True)
class Instrument:
    """A provider-neutral instrument identity.

    ``symbol`` is a canonical display code, not a provider-specific identifier.
    Each adapter owns translation to its upstream code convention.
    """

    symbol: str
    market: Market
    instrument_type: InstrumentType = InstrumentType.EQUITY
    currency: str = ""

    def __post_init__(self) -> None:
        normalized_symbol = self.symbol.strip().upper()
        normalized_symbol = _canonical_symbol(normalized_symbol, self.market)
        if not normalized_symbol:
            raise ValueError("symbol must not be empty")
        if any(character.isspace() for character in normalized_symbol):
            raise ValueError("symbol must not contain whitespace")
        object.__setattr__(self, "symbol", normalized_symbol)

        normalized_currency = self.currency.strip().upper() or _default_currency(self.market)
        if len(normalized_currency) != 3 or not normalized_currency.isalpha():
            raise ValueError("currency must be a three-letter ISO code")
        object.__setattr__(self, "currency", normalized_currency)


@dataclass(frozen=True, slots=True)
class Quote:
    """A single quote observed at a known instant.

    Prices deliberately use ``Decimal``: floats are not acceptable at a domain
    boundary where a future risk or order module may consume the value.
    """

    instrument: Instrument
    last_price: Decimal
    observed_at: datetime
    source: str
    open_price: Decimal | None = None
    high_price: Decimal | None = None
    low_price: Decimal | None = None
    previous_close: Decimal | None = None
    volume: Decimal | None = None

    def __post_init__(self) -> None:
        if self.last_price < 0:
            raise ValueError("last_price must not be negative")
        if self.observed_at.tzinfo is None:
            raise ValueError("observed_at must be timezone-aware")
        if not self.source.strip():
            raise ValueError("source must not be empty")
        object.__setattr__(self, "source", self.source.strip().lower())
        object.__setattr__(self, "observed_at", self.observed_at.astimezone(UTC))

        for name in ("open_price", "high_price", "low_price", "previous_close", "volume"):
            value = getattr(self, name)
            if value is not None and value < 0:
                raise ValueError(f"{name} must not be negative")


def _default_currency(market: Market) -> str:
    return {
        Market.A_SHARE: "CNY",
        Market.HONG_KONG: "HKD",
        Market.UNITED_STATES: "USD",
        Market.FUND: "CNY",
    }[market]


def _canonical_symbol(symbol: str, market: Market) -> str:
    """Accept a six-digit A-share input while retaining canonical venue codes."""
    if market is not Market.A_SHARE or not (symbol.isdigit() and len(symbol) == 6):
        return symbol
    suffix = {
        "6": "SH",
        "5": "SH",
        "9": "SH",
        "0": "SZ",
        "3": "SZ",
        "4": "BJ",
        "8": "BJ",
    }.get(symbol[0])
    return f"{symbol}.{suffix}" if suffix else symbol
