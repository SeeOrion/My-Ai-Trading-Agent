"""Short-lived identity lookup for forms and focused private lists."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from ai_trading_agent.application.instruments import ResolveInstrumentIdentityHandler
from ai_trading_agent.domain.aggregate.instrument_identity import InstrumentIdentity
from ai_trading_agent.domain.aggregate.market import Instrument
from ai_trading_agent.infrastructure.config.providers import HithinkFinanceSettings
from ai_trading_agent.infrastructure.rpc.hithink_instruments import (
    HithinkInstrumentIdentityProvider,
)
from ai_trading_agent.interfaces.adapter.environment import load_runtime_environment

_CACHE_TTL = timedelta(hours=12)
_identity_cache: dict[Instrument, tuple[datetime, InstrumentIdentity | None]] = {}


async def resolve_instrument_identity(instrument: Instrument) -> InstrumentIdentity | None:
    """Keep code entry responsive without making a database-backed name cache."""
    now = datetime.now(UTC)
    cached = _identity_cache.get(instrument)
    if cached is not None and now - cached[0] < _CACHE_TTL:
        return cached[1]
    load_runtime_environment()
    provider = HithinkInstrumentIdentityProvider(HithinkFinanceSettings.from_environment())
    identity = await ResolveInstrumentIdentityHandler(provider).handle(instrument)
    _identity_cache[instrument] = (now, identity)
    return identity
