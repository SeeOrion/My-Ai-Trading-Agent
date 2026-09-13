"""Use case for resolving a selected code to a verified display name."""

from __future__ import annotations

from typing import Protocol

from ai_trading_agent.domain.aggregate.instrument_identity import (
    CatalogInstrument,
    InstrumentIdentity,
)
from ai_trading_agent.domain.aggregate.market import Instrument


class InstrumentIdentityProvider(Protocol):
    async def resolve(self, instrument: Instrument) -> InstrumentIdentity | None: ...


class InstrumentCatalogProvider(Protocol):
    async def search(
        self, query: str, *, asset_types: tuple[str, ...], limit: int
    ) -> list[CatalogInstrument]: ...


class ResolveInstrumentIdentityHandler:
    def __init__(self, provider: InstrumentIdentityProvider) -> None:
        self._provider = provider

    async def handle(self, instrument: Instrument) -> InstrumentIdentity | None:
        return await self._provider.resolve(instrument)


class SearchInstrumentCatalogHandler:
    """Bound a catalogue lookup used to surface verifiable topic matches."""

    def __init__(self, provider: InstrumentCatalogProvider) -> None:
        self._provider = provider

    async def handle(
        self, query: str, *, asset_types: tuple[str, ...], limit: int = 6
    ) -> list[CatalogInstrument]:
        normalized_query = query.strip()
        if len(normalized_query) < 2:
            raise ValueError("catalogue query must contain at least two characters")
        if not asset_types:
            raise ValueError("at least one catalogue asset type is required")
        if not 1 <= limit <= 50:
            raise ValueError("catalogue limit must be between 1 and 50")
        return await self._provider.search(
            normalized_query, asset_types=asset_types, limit=limit
        )
