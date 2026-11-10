from datetime import UTC, datetime, timedelta
from decimal import Decimal as D
from unittest.mock import AsyncMock

import pytest

from ai_trading_agent.application.research_agent import ResearchAgent, optional_position_review
from ai_trading_agent.domain.service.agent_review import ResearchPolicy, review_entry


@pytest.mark.asyncio
@pytest.mark.parametrize("tokens,expected", [(None, "usage_unknown"), (100, "token_limit")])
async def test_usage_failure_never_returns_a_score(tokens, expected):
    from ai_trading_agent.application.research_agent import AgentLimits

    model = AsyncMock()
    model.step.return_value = {"total_tokens": tokens, "action": "finish", "report": {"score": 100}}
    result = await ResearchAgent(
        model, {}, validate_report=lambda report, trace: report, limits=AgentLimits(tokens=50)
    ).run({}, permitted=AsyncMock(return_value=True))
    assert result.status == expected and result.report is None


@pytest.mark.asyncio
async def test_timeout_retains_trace_without_a_score():
    import asyncio
    from ai_trading_agent.application.research_agent import AgentLimits

    model = AsyncMock()
    model.step.return_value = {"total_tokens": 1, "action": "tool", "tool": "news", "arguments": {}}

    async def tool(arguments):
        await asyncio.Event().wait()

    result = await ResearchAgent(
        model,
        {"news": tool},
        validate_report=lambda report, trace: report,
        limits=AgentLimits(timeout_seconds=0.01),
    ).run({}, permitted=AsyncMock(return_value=True))
    assert (
        result.status == "timeout" and result.report is None and result.trace[0]["tool"] == "news"
    )


def test_scoring_cannot_cancel_hard_constraints_or_fabricate_missing_scores():
    policy = ResearchPolicy()
    score, blockers = review_entry(
        policy,
        status="completed",
        workflow_score=D(90),
        research_score=D(100),
        hard_blockers=("纪律禁止",),
    )
    assert score == 94 and blockers == ("纪律禁止",)
    score, blockers = review_entry(
        policy, status="timeout", workflow_score=D(90), research_score=None, hard_blockers=()
    )
    assert score is None and "timeout" in blockers[0]
    with pytest.raises(ValueError):
        ResearchPolicy(workflow_weight=D("0.8"))


def test_post_research_quote_range_and_expiration():
    now = datetime.now(UTC)
    policy = ResearchPolicy()
    reasons = policy.quote_blockers(
        reference=D(10),
        current=D(11),
        researched_at=now - timedelta(minutes=6),
        quoted_at=now,
        now=now,
    )
    assert len(reasons) == 2


@pytest.mark.asyncio
async def test_off_never_calls_model_or_tools():
    model, tool = AsyncMock(), AsyncMock()
    agent = ResearchAgent(model, {"news": tool}, validate_report=lambda report, trace: report)
    result = await optional_position_review(
        agent, {}, current_generation=AsyncMock(return_value=None)
    )
    assert result.status == "disabled"
    model.step.assert_not_called()
    tool.assert_not_called()


@pytest.mark.asyncio
async def test_switch_change_during_model_call_discards_result():
    generation = [1]

    async def current():
        return generation[0]

    async def step(*args, **kwargs):
        generation[0] = None
        return {"total_tokens": 12, "action": "finish", "report": {"action": "exit"}}

    model = AsyncMock()
    model.step.side_effect = step
    agent = ResearchAgent(model, {}, validate_report=lambda report, trace: report)
    result = await optional_position_review(agent, {}, current_generation=current)
    assert result.status == "disabled" and result.report is None


@pytest.mark.asyncio
async def test_adaptive_tool_query_then_finish_and_repeat_limit():
    model, tool = AsyncMock(), AsyncMock(return_value={"source": "test", "fact": "verified"})
    query = {
        "action": "tool",
        "tool": "news",
        "arguments": {"symbol": "600737"},
        "total_tokens": 10,
    }
    model.step.side_effect = [
        query,
        {"action": "finish", "report": {"thesis": "test"}, "total_tokens": 10},
    ]
    agent = ResearchAgent(model, {"news": tool}, validate_report=lambda report, trace: report)
    result = await agent.run({}, permitted=AsyncMock(return_value=True))
    assert result.status == "completed" and result.tokens == 20
    assert result.trace[0]["evidence"]["source"] == "test"
    model.step.side_effect = [query, query]
    tool.reset_mock()
    result = await agent.run({}, permitted=AsyncMock(return_value=True))
    assert result.status == "repeat_limit" and tool.await_count == 1


@pytest.mark.asyncio
async def test_disable_interrupts_inflight_model_without_waiting_for_timeout():
    import asyncio

    entered, cancelled = asyncio.Event(), asyncio.Event()
    version = [1]

    async def current():
        return version[0]

    async def step(*args, **kwargs):
        entered.set()
        try:
            await asyncio.Event().wait()
        finally:
            cancelled.set()

    model = AsyncMock()
    model.step.side_effect = step
    agent = ResearchAgent(model, {}, validate_report=lambda report, trace: report)
    task = asyncio.create_task(optional_position_review(agent, {}, current_generation=current))
    await entered.wait()
    version[0] = 2  # Even disabling and re-enabling cannot revive old work.
    result = await asyncio.wait_for(task, timeout=1)
    assert result.status == "disabled" and result.report is None and cancelled.is_set()


def test_evidence_validation_rejects_fabricated_citations_and_risk_quotes():
    from copy import deepcopy
    from ai_trading_agent.domain.service.agent_evidence import (
        validate_agent_report,
        InsufficientEvidence,
    )

    trace = [
        {"tool": name, "status": "completed", "evidence": {"text": "已披露的真实来源原文证据"}}
        for name in ("news", "financials", "quote")
    ]
    claim = lambda ref: {"text": "基于来源", "evidence_ids": [str(ref)]}
    report = {
        "dimensions": {
            name: {**claim(i), "score": 80}
            for i, name in enumerate(
                ("event_veracity", "earnings_persistence", "thesis_resilience")
            )
        },
        "thesis": claim(0),
        "price_min": 9,
        "price_max": 11,
        "recommendation": "buy",
        "risks": [],
    }
    assert validate_agent_report(report, trace)["score"] == "80.00"
    invalid = deepcopy(report)
    invalid["thesis"]["evidence_ids"] = ["99"]
    with pytest.raises(InsufficientEvidence):
        validate_agent_report(invalid, trace)
    report["risks"] = [
        {**claim(0), "severity": "critical", "source_quote": "模型自行编造的风险引用内容"}
    ]
    with pytest.raises(InsufficientEvidence):
        validate_agent_report(report, trace)
