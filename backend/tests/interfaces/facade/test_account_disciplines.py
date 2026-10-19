from dataclasses import replace
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from fastapi import FastAPI

from ai_trading_agent.application.disciplines import EvaluateInstrumentDisciplinesHandler
from ai_trading_agent.domain.aggregate.ai_simulation import AiSimulationPortfolio
from ai_trading_agent.domain.enums.market import Market
from ai_trading_agent.domain.enums.research import DisciplineStatus
from ai_trading_agent.interfaces.facade import ai_simulation as service
from ai_trading_agent.interfaces.facade import disciplines


@pytest.mark.asyncio
async def test_only_selected_rule_evaluated(monkeypatch):
    first, second = uuid4(), uuid4()
    instrument = object()
    rules = [
        SimpleNamespace(discipline_id=i, instrument=instrument, status=DisciplineStatus.ACTIVE)
        for i in (first, second)
    ]
    monkeypatch.setattr(
        "ai_trading_agent.application.disciplines.evaluate_discipline",
        lambda rule, quote: rule.discipline_id,
    )
    handler = EvaluateInstrumentDisciplinesHandler(
        SimpleNamespace(list=AsyncMock(return_value=rules))
    )
    quote = SimpleNamespace(instrument=instrument)
    assert await handler.handle(instrument, quote, (first,)) == [first]
    assert await handler.handle(instrument, quote, (second,)) == [second]
    assert await handler.handle(instrument, quote, ()) == []


@pytest.mark.asyncio
async def test_empty_selection_does_not_load_global_disciplines(monkeypatch):
    def forbidden(app):
        raise AssertionError("must not read global rules")

    monkeypatch.setattr(disciplines, "discipline_repository", forbidden)
    assert await disciplines.evaluate_active_disciplines(FastAPI(), None, None, ()) == []


@pytest.mark.asyncio
async def test_invalid_selection_rejected(monkeypatch):
    monkeypatch.setattr(service, "get_discipline", AsyncMock(return_value=None))
    with pytest.raises(ValueError, match="不存在"):
        await service._validate_account_disciplines(FastAPI(), Market.A_SHARE, (uuid4(),))


@pytest.mark.asyncio
async def test_independent_configuration_and_scheduler(monkeypatch):
    first = AiSimulationPortfolio(
        uuid4(), "a_share", "CNY", Decimal(10000), Decimal(10000), 3, discipline_ids=(uuid4(),)
    )
    second = replace(
        first,
        portfolio_id=uuid4(),
        initial_capital=Decimal(20000),
        cash_balance=Decimal(20000),
        discipline_ids=(uuid4(),),
    )
    repo = SimpleNamespace(
        list_active=AsyncMock(return_value=[first, second]),
        save_portfolio=AsyncMock(side_effect=lambda item: item),
    )
    request = service.AiSimulationRunRequest(
        Market.A_SHARE, Decimal(12000), portfolio_id=first.portfolio_id, discipline_ids=()
    )
    changed = await service._save_reconfigured_portfolio(repo, first, [], request, ())
    assert changed.discipline_ids == () and changed.cash_balance == Decimal(12000)
    assert second.cash_balance == Decimal(20000) and second.discipline_ids
    calls = []

    async def record(app, request):
        calls.append((request.portfolio_id, request.discipline_ids))

    monkeypatch.setattr(service, "ai_simulation_repository", lambda app: repo)
    monkeypatch.setattr(service, "run_ai_simulation", record)
    await service.run_scheduled_ai_simulations(
        FastAPI(),
        trading_calendar=SimpleNamespace(is_trading_day=lambda *a: True, is_open=lambda *a: True),
    )
    assert calls == [
        (first.portfolio_id, first.discipline_ids),
        (second.portfolio_id, second.discipline_ids),
    ]
