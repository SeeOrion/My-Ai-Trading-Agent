from datetime import UTC, datetime
from decimal import Decimal as D
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from ai_trading_agent.domain.aggregate.ai_simulation import AiSimulationPortfolio
from ai_trading_agent.domain.aggregate.candidate import CandidateObservation, RankedCandidate
from ai_trading_agent.domain.aggregate.market import Instrument, Quote
from ai_trading_agent.domain.enums.market import Market
from ai_trading_agent.domain.service.ai_simulation import AiSimulationCandidate
from ai_trading_agent.interfaces.model.agent import AgentSettings
from ai_trading_agent.interfaces.facade import (
    research_agents as agents,
    ai_simulation as simulation,
    research_workspace,
)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "status,price,discipline",
    [
        ("timeout", "10", ()),
        ("insufficient_evidence", "10", ()),
        ("completed", "11", ()),
        ("completed", "10", ("纪律禁止",)),
        ("completed", "10", ()),
    ],
)
async def test_buy_gate_status_price_and_hard_constraints(monkeypatch, status, price, discipline):
    instrument = Instrument("600737.SH", Market.A_SHARE)
    candidate = RankedCandidate(
        CandidateObservation(
            instrument, "测试", D(10), D(1), D(10000), D(11), D(9), datetime.now(UTC), "test"
        ),
        D(80),
        ("基础评分",),
    )
    portfolio = AiSimulationPortfolio(uuid4(), "a_share", "CNY", D(100000), D(100000), 3)
    simulated = AiSimulationCandidate(
        instrument.symbol, "测试", D(80), D(10), 2, 0, ("a", "b"), (), ()
    )
    payload = {
        "generation": 1,
        "status": status,
        "started_at": datetime.now(UTC).isoformat(),
        "report": {
            "score": "90",
            "recommendation": "buy",
            "risks": [],
            "price_min": "9",
            "price_max": "10.5",
        }
        if status == "completed"
        else None,
    }
    repo = SimpleNamespace(finish=AsyncMock())
    monkeypatch.setattr(agents, "repository", lambda app: repo)
    monkeypatch.setattr(
        agents, "run_research", AsyncMock(return_value=("audit", payload, AgentSettings()))
    )
    monkeypatch.setattr(agents, "settings", AsyncMock(return_value=(1, AgentSettings())))
    monkeypatch.setattr(
        simulation, "_discipline_entry_blockers", AsyncMock(return_value=discipline)
    )
    monkeypatch.setattr(
        research_workspace,
        "latest_quote",
        AsyncMock(return_value=Quote(instrument, D(price), datetime.now(UTC), "test")),
    )
    result, decision = await agents.buy_review(
        object(), candidate, portfolio, (), 0, simulated, SimpleNamespace(blockers=())
    )
    assert (decision.allocation is not None) == (
        status == "completed" and price == "10" and not discipline
    )
    if status == "completed":
        assert result.score == 84
    else:
        assert repo.finish.call_args.args[1]["combined_score"] is None


@pytest.mark.asyncio
async def test_position_disabled_preserves_baseline_objects_and_no_research(monkeypatch):
    portfolio = SimpleNamespace(portfolio_id=uuid4())
    positions = [object(), object()]
    run = AsyncMock()
    monkeypatch.setattr(agents, "settings", AsyncMock(return_value=(1, AgentSettings())))
    monkeypatch.setattr(agents, "run_research", run)
    result = await agents.review_positions(object(), object(), portfolio, positions, ())
    assert result[0] is portfolio and result[1] is positions and result[2] == ()
    run.assert_not_called()
