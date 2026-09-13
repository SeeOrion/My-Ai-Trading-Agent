"""A verified display identity for one user-selected instrument."""

from __future__ import annotations

from dataclasses import dataclass

from ai_trading_agent.domain.aggregate.market import Instrument


@dataclass(frozen=True, slots=True)
class InstrumentIdentity:
    instrument: Instrument
    display_name: str
    source: str

    def __post_init__(self) -> None:
        if not self.display_name.strip():
            raise ValueError("display_name must not be empty")
        if not self.source.strip():
            raise ValueError("source must not be empty")
        object.__setattr__(self, "display_name", self.display_name.strip())
        object.__setattr__(self, "source", self.source.strip().lower())


@dataclass(frozen=True, slots=True)
class CatalogInstrument:
    """A source-attributed instrument returned by a catalogue search.

    Unlike ``InstrumentIdentity``, a catalogue item is intentionally not a
    user-selected instrument.  It preserves the provider's asset category so
    presentation code can show possible matches without guessing a market.
    """

    symbol: str
    name: str
    asset_type: str
    exchange: str | None
    currency: str | None
    source: str

    def __post_init__(self) -> None:
        if not self.symbol.strip() or not self.name.strip() or not self.asset_type.strip():
            raise ValueError("catalogue instrument fields must not be empty")
        if not self.source.strip():
            raise ValueError("source must not be empty")
        object.__setattr__(self, "symbol", self.symbol.strip().upper())
        object.__setattr__(self, "name", self.name.strip())
        object.__setattr__(self, "asset_type", self.asset_type.strip().lower())
        object.__setattr__(self, "exchange", _optional_upper(self.exchange))
        object.__setattr__(self, "currency", _optional_upper(self.currency))
        object.__setattr__(self, "source", self.source.strip().lower())


def _optional_upper(value: str | None) -> str | None:
    normalized = (value or "").strip().upper()
    return normalized or None
