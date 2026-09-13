from decimal import Decimal

from ai_trading_agent.domain.service.ai_simulation import (
    AiSimulationCandidate,
    choose_simulated_entry,
    evaluate_simulated_entry,
)


def _candidate(
    *, score: str = "82", supportive: int = 3, adverse: int = 1, price: str = "10"
) -> AiSimulationCandidate:
    return AiSimulationCandidate(
        symbol="600519.SH",
        display_name="贵州茅台",
        score=Decimal(score),
        last_price=Decimal(price),
        supportive_factor_count=supportive,
        adverse_factor_count=adverse,
        available_factor_ids=("momentum_20d", "relative_volume_20d"),
        unavailable_factor_ids=(),
        rationale=("趋势和量能数据支持。",),
    )


def test_ai_simulation_uses_risk_budget_and_a_share_board_lots() -> None:
    allocation = choose_simulated_entry(
        _candidate(),
        available_cash=Decimal("100000"),
        initial_capital=Decimal("100000"),
        open_position_count=0,
        max_positions=3,
        max_position_percent=Decimal("25"),
        lot_size=Decimal("100"),
    )

    assert allocation is not None
    assert allocation.quantity == Decimal("2500")
    assert allocation.amount == Decimal("25000")
    assert allocation.allocation_percent == Decimal("25")


def test_ai_simulation_keeps_cash_when_factor_evidence_or_score_is_insufficient() -> None:
    allocation = choose_simulated_entry(
        _candidate(score="69", supportive=1, adverse=1),
        available_cash=Decimal("100000"),
        initial_capital=Decimal("100000"),
        open_position_count=0,
        max_positions=3,
        max_position_percent=Decimal("25"),
        lot_size=Decimal("100"),
    )

    assert allocation is None


def test_ai_simulation_explains_each_rejected_entry_condition() -> None:
    candidate = AiSimulationCandidate(
        symbol="600519.SH",
        display_name="贵州茅台",
        score=Decimal("65"),
        last_price=Decimal("1500"),
        supportive_factor_count=0,
        adverse_factor_count=2,
        available_factor_ids=(),
        unavailable_factor_ids=("return_on_equity", "earnings_yield"),
        rationale=("数据不完整。",),
    )

    decision = evaluate_simulated_entry(
        candidate,
        available_cash=Decimal("10000"),
        initial_capital=Decimal("10000"),
        open_position_count=3,
        max_positions=3,
        max_position_percent=Decimal("25"),
        lot_size=Decimal("100"),
    )

    assert decision.allocation is None
    assert any("评分" in item for item in decision.blockers)
    assert any("缺失" in item for item in decision.blockers)
    assert any("支持 0 项，逆风 2 项" in item for item in decision.blockers)
    assert any("达到上限" in item for item in decision.blockers)
