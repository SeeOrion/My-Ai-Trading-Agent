"""Use case for resolving a selected code to a verified display name."""

from __future__ import annotations

from typing import Protocol

from ai_trading_agent.domain.aggregate.instrument_identity import InstrumentIdentity
from ai_trading_agent.domain.aggregate.market import Instrument


class InstrumentIdentityProvider(Protocol):
    async def resolve(self, instrument: Instrument) -> InstrumentIdentity | None: ...


class ResolveInstrumentIdentityHandler:
    def __init__(self, provider: InstrumentIdentityProvider) -> None:
        self._provider = provider

    async def handle(self, instrument: Instrument) -> InstrumentIdentity | None:
        return await self._provider.resolve(instrument)
