"""Use case for the small, explicit post-market overview."""

from __future__ import annotations

from typing import Protocol

from ai_trading_agent.domain.aggregate.market_brief import PostMarketBrief


class MarketBriefProvider(Protocol):
    """A provider that can supply named index and industry snapshots."""

    async def get_post_market_brief(self) -> PostMarketBrief: ...


class GetPostMarketBriefHandler:
    def __init__(self, provider: MarketBriefProvider) -> None:
        self._provider = provider

    async def handle(self) -> PostMarketBrief:
        return await self._provider.get_post_market_brief()
