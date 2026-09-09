"""Use case for retrieving one selected fund or ETF research workspace."""

from __future__ import annotations

from ai_trading_agent.application.ports import FundResearchProvider
from ai_trading_agent.domain.aggregate.fund import FundResearchReport
from ai_trading_agent.domain.aggregate.market import Instrument


class GetFundResearchHandler:
    def __init__(self, provider: FundResearchProvider) -> None:
        self._provider = provider

    async def handle(self, instrument: Instrument) -> FundResearchReport:
        return await self._provider.get_fund_research(instrument)
