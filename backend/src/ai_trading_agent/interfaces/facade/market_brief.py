"""Cached composition root for the small dashboard market brief."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from ai_trading_agent.application.market_brief import GetPostMarketBriefHandler
from ai_trading_agent.domain.aggregate.market_brief import PostMarketBrief
from ai_trading_agent.infrastructure.config.providers import HithinkFinanceSettings
from ai_trading_agent.infrastructure.rpc.hithink_market_brief import HithinkMarketBriefProvider
from ai_trading_agent.interfaces.adapter.environment import load_runtime_environment

_CACHE_TTL = timedelta(minutes=15)
_cached_brief: tuple[datetime, PostMarketBrief] | None = None


async def post_market_brief(*, refresh: bool = False) -> PostMarketBrief:
    """Use a short cache so navigation never repeatedly queries all industry indices."""
    global _cached_brief
    now = datetime.now(UTC)
    if not refresh and _cached_brief is not None and now - _cached_brief[0] < _CACHE_TTL:
        return _cached_brief[1]
    load_runtime_environment()
    provider = HithinkMarketBriefProvider(HithinkFinanceSettings.from_environment())
    brief = await GetPostMarketBriefHandler(provider).handle()
    _cached_brief = (now, brief)
    return brief
