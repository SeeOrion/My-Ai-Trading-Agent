from datetime import UTC, datetime, timedelta
from decimal import Decimal as D
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from ai_trading_agent.domain.aggregate.ai_simulation import AiSimulationPortfolio
from ai_trading_agent.domain.aggregate.candidate import CandidateObservation, RankedCandidate
from ai_trading_agent.domain.aggregate.market import Instrument
from ai_trading_agent.domain.enums.market import Market
from ai_trading_agent.interfaces.facade import ai_simulation as facade


def candidate(symbol="600737.SH", *, observed_at=None):
    return RankedCandidate(
        CandidateObservation(
            Instrument(symbol, Market.A_SHARE),
            "测试股票",
            D("10"),
            D("1"),
            D("10000"),
            D("11"),
            D("9"),
            observed_at or datetime.now(UTC),
            "test",
        ),
        D("80"),
        ("样本综合排名靠前",),
    )


def analysis(direction="supportive"):
    return {
        "observations": [
            {"identifier": name, "direction": direction, "interpretation": "测试因子"}
            for name in ("momentum_20d", "relative_volume_20d")
        ]
    }


@pytest.mark.asyncio
async def test_preview_reuses_entry_checks_caps_three_and_never_writes(monkeypatch):
    repo = SimpleNamespace(get_active=AsyncMock(return_value=None))  # No write methods!
    monkeypatch.setattr(facade, "ai_simulation_repository", lambda app: repo)
    monkeypatch.setattr(facade, "builtin_factor_analysis", AsyncMock(return_value=analysis()))
    monkeypatch.setattr(facade, "_discipline_entry_blockers", AsyncMock(return_value=()))
    monkeypatch.setattr(
        facade,
        "today_candidates",
        AsyncMock(
            return_value=(
                SimpleNamespace(
                    candidates=[candidate(f"60000{i}.SH") for i in range(5)], universe_size=5
                ),
                datetime.now(UTC),
            )
        ),
    )
    result = await facade.best_entry_candidates(object(), Market.A_SHARE)
    assert len(result["candidates"]) == 3
    assert result["candidates"][0]["symbol"] == "600000.SH"
    assert not result["excluded"]
    assert "尚无模拟账户" in result["account_basis"]


@pytest.mark.asyncio
@pytest.mark.parametrize("blocker", ["stale", "discipline", "budget", "adverse"])
async def test_shared_gate_reports_actual_rejection(monkeypatch, blocker):
    portfolio = AiSimulationPortfolio(
        uuid4(), "a_share", "CNY", D("100000"), D("0") if blocker == "budget" else D("100000"), 3
    )
    monkeypatch.setattr(
        facade,
        "builtin_factor_analysis",
        AsyncMock(return_value=analysis("adverse" if blocker == "adverse" else "supportive")),
    )
    monkeypatch.setattr(
        facade,
        "_discipline_entry_blockers",
        AsyncMock(return_value=("个人纪律价格未满足",) if blocker == "discipline" else ()),
    )
    item = (
        candidate(observed_at=datetime.now(UTC) - timedelta(hours=2))
        if blocker == "stale"
        else candidate()
    )
    _, decision = await facade.assess_entry_candidate(object(), item, portfolio, (), 0)
    assert decision.allocation is None
    assert decision.blockers


@pytest.mark.asyncio
async def test_missing_factors_are_not_automatically_a_rejection(monkeypatch):
    portfolio = AiSimulationPortfolio(uuid4(), "a_share", "CNY", D("100000"), D("100000"), 3)
    monkeypatch.setattr(
        facade, "builtin_factor_analysis", AsyncMock(return_value=analysis("unavailable"))
    )
    monkeypatch.setattr(facade, "_discipline_entry_blockers", AsyncMock(return_value=()))
    simulated, decision = await facade.assess_entry_candidate(
        object(), candidate(), portfolio, (), 0
    )
    assert decision.allocation is not None
    assert len(simulated.unavailable_factor_ids) == 2
