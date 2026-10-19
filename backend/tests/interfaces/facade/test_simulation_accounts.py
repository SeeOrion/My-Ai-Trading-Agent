import asyncio
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from fastapi import FastAPI

from ai_trading_agent.domain.aggregate.ai_simulation import AiSimulationPortfolio
from ai_trading_agent.domain.enums.market import Market
from ai_trading_agent.interfaces.facade import ai_simulation as service


def account():
    return AiSimulationPortfolio(uuid4(), "a_share", "CNY", Decimal(10000), Decimal(10000), 3)


@pytest.mark.asyncio
async def test_explicit_account_and_ambiguous_legacy_request():
    first, second = account(), account()
    repo = SimpleNamespace(
        get=AsyncMock(return_value=first), list_active=AsyncMock(return_value=[first, second])
    )
    assert (
        await service.resolve_simulation_account(repo, Market.A_SHARE, first.portfolio_id) == first
    )
    with pytest.raises(ValueError, match="多个"):
        await service.resolve_simulation_account(repo, Market.A_SHARE)
    with pytest.raises(ValueError, match="不匹配"):
        await service.resolve_simulation_account(repo, Market.HONG_KONG, first.portfolio_id)
    repo.get.return_value = None
    with pytest.raises(ValueError, match="不存在"):
        await service.resolve_simulation_account(repo, Market.A_SHARE, uuid4())


@pytest.mark.asyncio
async def test_runs_are_filtered_by_selected_account(monkeypatch):
    first = account()
    repo = SimpleNamespace(get=AsyncMock(return_value=first), list_runs=AsyncMock(return_value=[]))
    monkeypatch.setattr(service, "ai_simulation_repository", lambda app: repo)
    assert await service.ai_simulation_runs(FastAPI(), Market.A_SHARE, 14, first.portfolio_id) == []
    repo.list_runs.assert_awaited_once_with(Market.A_SHARE, 14, first.portfolio_id)


@pytest.mark.asyncio
async def test_scheduler_dispatches_every_account_by_id(monkeypatch):
    first, second = account(), account()
    repo = SimpleNamespace(list_active=AsyncMock(return_value=[first, second]))
    calls = []

    async def run(app, request):
        calls.append(request.portfolio_id)

    monkeypatch.setattr(service, "ai_simulation_repository", lambda app: repo)
    monkeypatch.setattr(service, "run_ai_simulation", run)
    calendar = SimpleNamespace(is_trading_day=lambda *a: True, is_open=lambda *a: True)
    await service.run_scheduled_ai_simulations(FastAPI(), trading_calendar=calendar)
    assert calls == [first.portfolio_id, second.portfolio_id]


@pytest.mark.asyncio
async def test_creation_only_saves_account(monkeypatch):
    repo = SimpleNamespace(save_portfolio=AsyncMock(side_effect=lambda a: a))
    monkeypatch.setattr(service, "ai_simulation_repository", lambda app: repo)
    request = service.AiSimulationRunRequest(Market.A_SHARE, Decimal(20000))
    a = await service.create_simulation_account(FastAPI(), request)
    b = await service.create_simulation_account(FastAPI(), request)
    assert a.portfolio_id != b.portfolio_id and a.cash_balance == Decimal(20000)
    assert repo.save_portfolio.await_count == 2


@pytest.mark.asyncio
async def test_same_account_busy_does_not_run_twice(monkeypatch):
    first = account()
    repo = SimpleNamespace(get=AsyncMock(return_value=first))
    monkeypatch.setattr(service, "ai_simulation_repository", lambda app: repo)
    app = FastAPI()
    lock = asyncio.Lock()
    app.state.simulation_account_locks = {str(first.portfolio_id): lock}
    request = service.AiSimulationRunRequest(
        Market.A_SHARE, Decimal(10000), portfolio_id=first.portfolio_id
    )
    action = AsyncMock()
    async with lock:
        with pytest.raises(ValueError, match="正在复核"):
            await service._with_account_lock(app, request, action)
    action.assert_not_awaited()
