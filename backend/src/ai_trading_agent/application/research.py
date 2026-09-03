"""Use cases for the Research bounded context."""

from __future__ import annotations

from typing import Protocol

from ai_trading_agent.domain.aggregate.market import Instrument
from ai_trading_agent.domain.aggregate.research import (
    CapitalFlowAssessment,
    CapitalFlowSnapshot,
    FinancialSnapshot,
    FundamentalAssessment,
    OptionStrategy,
    OptionStrategyAssessment,
    SentimentAssessment,
    analyze_financial_sentiment,
    assess_capital_flow,
    assess_fundamentals,
    assess_option_strategy,
)


class FundamentalsProvider(Protocol):
    async def get_financial_snapshot(self, instrument: Instrument) -> FinancialSnapshot:
        """Return the latest published financial snapshot for an instrument."""


class CapitalFlowProvider(Protocol):
    async def get_capital_flow(self, instrument: Instrument) -> CapitalFlowSnapshot:
        """Return the latest reported capital flow for an instrument."""


class AnalyzeFundamentalsHandler:
    def __init__(self, provider: FundamentalsProvider) -> None:
        self._provider = provider

    async def handle(self, instrument: Instrument) -> FundamentalAssessment:
        return assess_fundamentals(await self._provider.get_financial_snapshot(instrument))


class AnalyzeCapitalFlowHandler:
    def __init__(self, provider: CapitalFlowProvider) -> None:
        self._provider = provider

    async def handle(self, instrument: Instrument) -> CapitalFlowAssessment:
        return assess_capital_flow(await self._provider.get_capital_flow(instrument))


def analyze_sentiment(text: str) -> SentimentAssessment:
    return analyze_financial_sentiment(text)


def analyze_option_strategy(strategy: OptionStrategy) -> OptionStrategyAssessment:
    return assess_option_strategy(strategy)
