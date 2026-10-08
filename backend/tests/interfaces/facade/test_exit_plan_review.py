from dataclasses import replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal as D
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4
from zoneinfo import ZoneInfo

import pytest

from ai_trading_agent.domain.aggregate.ai_simulation import (
    AiSimulationPortfolio,
    AiSimulationPosition,
)
from ai_trading_agent.domain.aggregate.market import Instrument, Quote
from ai_trading_agent.domain.enums.market import Market
from ai_trading_agent.domain.enums.research import DisciplineDecisionStatus
from ai_trading_agent.domain.service.simulation_exit import SimulationExitEvidence
from ai_trading_agent.infrastructure.repo.ai_simulation import _exit_plan
from ai_trading_agent.interfaces.facade import ai_simulation as facade
from ai_trading_agent.interfaces.model.http import PositionExitPlanResponse


def state(*, today=False):
    now = datetime.now(UTC)
    portfolio = AiSimulationPortfolio(uuid4(), "a_share", "CNY", D("100000"), D("10000"), 3)
    position = AiSimulationPosition(
        uuid4(),
        portfolio.portfolio_id,
        Instrument("600737.SH", Market.A_SHARE),
        D("1000"),
        D("100"),
        now if today else now - timedelta(days=2),
        D("80"),
        ("momentum_20d",),
        ("测试",),
        D("100"),
    )
    quote = Quote(position.instrument, D("90"), now, "test")
    evidence = SimulationExitEvidence(D("90"), D("100"), D("1000"), D("100"), 0, D("100"))
    return portfolio, position, quote, evidence


@pytest.mark.asyncio
@pytest.mark.parametrize("mode", ["t_plus_one", "personal_discipline", "automatic", "stale"])
async def test_each_holding_review_preserves_guards_and_plan(monkeypatch, mode):
    portfolio, position, quote, evidence = state(today=mode == "t_plus_one")
    if mode == "stale":
        quote = replace(quote, observed_at=quote.observed_at - timedelta(days=1))
    repo = SimpleNamespace(save_position=AsyncMock(side_effect=lambda value: value))
    monkeypatch.setattr(facade, "latest_quote", AsyncMock(return_value=quote))
    monkeypatch.setattr(
        facade, "_automatic_exit_evidence", AsyncMock(return_value=(evidence, "资讯暂缺"))
    )
    decisions = (
        [
            SimpleNamespace(
                status=DisciplineDecisionStatus.OBSERVE, discipline=SimpleNamespace(name="个人规则")
            )
        ]
        if mode == "personal_discipline"
        else []
    )
    monkeypatch.setattr(facade, "evaluate_active_disciplines", AsyncMock(return_value=decisions))
    sale = AsyncMock(return_value=(portfolio, None, "已模拟退出"))
    monkeypatch.setattr(facade, "_execute_position_sale", sale)
    _, positions, notices = await facade._apply_position_exits(
        object(), repo, portfolio, [position], ()
    )
    if mode == "automatic":
        sale.assert_awaited_once()
        assert sale.call_args.args[2].exit_plan.action == "full_exit"
        assert not positions
    else:
        sale.assert_not_awaited()
        assert len(positions) == 1
        if mode == "stale":
            assert positions[0].exit_plan is None
            assert "过期" in notices[0]
        else:
            assert positions[0].exit_plan.action == (
                "settlement_hold" if mode == "t_plus_one" else "discipline_hold"
            )


@pytest.mark.asyncio
@pytest.mark.parametrize("days_ago, expected", [(0, True), (1, False)])
async def test_only_same_day_flow_can_tighten_plan(monkeypatch, days_ago, expected):
    _, position, quote, _ = state()
    monkeypatch.setattr(
        facade,
        "historical_bars_provider",
        lambda instrument: SimpleNamespace(
            get_daily_bars=AsyncMock(side_effect=RuntimeError("测试无日线"))
        ),
    )
    trade_date = quote.observed_at.astimezone(ZoneInfo("Asia/Shanghai")).date() - timedelta(
        days=days_ago
    )
    monkeypatch.setattr(
        facade,
        "research",
        AsyncMock(
            return_value=SimpleNamespace(
                factor_analysis=None,
                fundamentals=None,
                news_sentiment=None,
                notices=[],
                capital_flow={
                    "trade_date": trade_date.isoformat(),
                    "direction": "outflow",
                    "institutional_direction": "outflow",
                    "source": "test",
                },
            )
        ),
    )
    evidence, _ = await facade._automatic_exit_evidence(position, quote, ())
    assert evidence.fresh_flow_out is expected


def test_exit_plan_json_round_trip_preserves_decimals_and_http_contract():
    payload = {
        "stop_price": "9.87654321",
        "target_price": "12.34",
        "reviewed_at": datetime.now(UTC).isoformat(),
        "action": "hold",
        "basis": ["价格证据"],
        "data_notes": ["情绪暂缺"],
        "version": "adaptive_v2",
    }
    plan = _exit_plan(payload)
    assert plan.stop_price == D("9.87654321")
    response = PositionExitPlanResponse.model_validate(plan).model_dump(mode="json")
    assert datetime.fromisoformat(response.pop("reviewed_at")) == plan.reviewed_at
    assert response == {key: value for key, value in payload.items() if key != "reviewed_at"}
    assert _exit_plan(None) is None
