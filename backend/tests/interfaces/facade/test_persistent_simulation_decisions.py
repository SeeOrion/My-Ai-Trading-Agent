from datetime import UTC, datetime
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from fastapi import FastAPI

from ai_trading_agent.domain.aggregate.ai_simulation import AiSimulationPortfolio
from ai_trading_agent.domain.enums.market import Market
from ai_trading_agent.interfaces.facade import ai_simulation as service


@pytest.mark.asyncio
@pytest.mark.parametrize("close_only", [False, True])
async def test_refresh_keeps_latest_account_decisions_until_next_run(monkeypatch, close_only):
    account = AiSimulationPortfolio(uuid4(), "a_share", "CNY", Decimal(10000), Decimal(10000), 3)
    reports = (SimpleNamespace(symbol="510300.SH", blockers=("风险预算不足",)),)
    repo = SimpleNamespace(
        get=AsyncMock(return_value=account),
        list_open_positions=AsyncMock(return_value=[]),
        list_runs=AsyncMock(return_value=[SimpleNamespace(decision_reports=reports)]),
    )
    monkeypatch.setattr(service, "ai_simulation_repository", lambda app: repo)
    monkeypatch.setattr(service, "closing_price_repository", lambda app: None)
    monkeypatch.setattr(service, "paper_portfolio_overview", AsyncMock(return_value=SimpleNamespace(
        valuations=[], notices=(), summary=SimpleNamespace(currencies=[], observed_at=datetime.now(UTC))
    )))
    monkeypatch.setattr(service, "_display_names", AsyncMock(return_value={}))
    for _ in range(2):
        overview = await service.ai_simulation_overview(FastAPI(), Market.A_SHARE, close_only=close_only, portfolio_id=account.portfolio_id)
        assert overview.decision_reports == reports
    repo.list_runs.assert_awaited_with(Market.A_SHARE, 1, account.portfolio_id)
    # New runs (including failed/empty runs) replace rather than revive old blockers.
    repo.list_runs.return_value = [SimpleNamespace(decision_reports=())]
    overview = await service.ai_simulation_overview(FastAPI(), Market.A_SHARE, portfolio_id=account.portfolio_id)
    assert overview.decision_reports == ()
    repo.list_runs.return_value = []
    overview = await service.ai_simulation_overview(FastAPI(), Market.A_SHARE, portfolio_id=account.portfolio_id)
    assert overview.decision_reports == ()
