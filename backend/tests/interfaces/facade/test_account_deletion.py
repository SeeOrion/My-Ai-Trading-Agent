import asyncio
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from fastapi import FastAPI

from ai_trading_agent.domain.aggregate.ai_simulation import AiSimulationPortfolio
from ai_trading_agent.interfaces.facade import ai_simulation as service


@pytest.mark.asyncio
async def test_delete_archives_only_requested_account(monkeypatch):
    account = AiSimulationPortfolio(uuid4(), "a_share", "CNY", Decimal(10000), Decimal(5000), 3)
    repo = SimpleNamespace(get=AsyncMock(return_value=account), save_portfolio=AsyncMock())
    monkeypatch.setattr(service, "ai_simulation_repository", lambda app: repo)
    await service.delete_simulation_account(FastAPI(), account.portfolio_id)
    archived = repo.save_portfolio.call_args.args[0]
    assert archived.status == "archived"
    assert archived.portfolio_id == account.portfolio_id
    assert archived.cash_balance == account.cash_balance
    assert archived.initial_capital == account.initial_capital


@pytest.mark.asyncio
async def test_delete_busy_account_is_rejected():
    app = FastAPI()
    identifier = uuid4()
    lock = asyncio.Lock()
    app.state.simulation_account_locks = {str(identifier): lock}
    async with lock:
        with pytest.raises(ValueError, match="正在复核"):
            await service.delete_simulation_account(app, identifier)


@pytest.mark.asyncio
async def test_deleted_account_cannot_be_resolved(monkeypatch):
    account = AiSimulationPortfolio(
        uuid4(), "a_share", "CNY", Decimal(10000), Decimal(10000), 3, status="archived"
    )
    from ai_trading_agent.domain.enums.market import Market

    repo = SimpleNamespace(get=AsyncMock(return_value=account))
    with pytest.raises(ValueError, match="未启用"):
        await service.resolve_simulation_account(repo, Market.A_SHARE, account.portfolio_id)
