from datetime import date
from decimal import Decimal

import pytest

from ai_trading_agent.application.research import (
    AnalyzeCapitalFlowHandler,
    AnalyzeFundamentalsHandler,
)
from ai_trading_agent.domain.aggregate.market import Instrument
from ai_trading_agent.domain.aggregate.research import CapitalFlowSnapshot, FinancialSnapshot
from ai_trading_agent.domain.enums.market import Market


class FakeResearchProvider:
    async def get_financial_snapshot(self, instrument: Instrument) -> FinancialSnapshot:
        return FinancialSnapshot(
            instrument,
            date(2026, 8, 30),
            date(2026, 6, 30),
            return_on_equity_pct=Decimal("16"),
            source="fake",
        )

    async def get_capital_flow(self, instrument: Instrument) -> CapitalFlowSnapshot:
        return CapitalFlowSnapshot(instrument, date(2026, 9, 1), Decimal("1"), Decimal("1"), "fake")


@pytest.mark.asyncio
async def test_fundamental_handler_orchestrates_provider_and_domain_service() -> None:
    assessment = await AnalyzeFundamentalsHandler(FakeResearchProvider()).handle(
        Instrument("600519.SH", Market.A_SHARE)
    )

    assert assessment.score == 2


@pytest.mark.asyncio
async def test_capital_flow_handler_orchestrates_provider_and_domain_service() -> None:
    assessment = await AnalyzeCapitalFlowHandler(FakeResearchProvider()).handle(
        Instrument("600519.SH", Market.A_SHARE)
    )

    assert assessment.direction == "inflow"
