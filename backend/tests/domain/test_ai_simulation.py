from decimal import Decimal
from uuid import uuid4

from ai_trading_agent.domain.aggregate.ai_simulation import AiSimulationPortfolio
from ai_trading_agent.domain.service.ai_simulation import (
    AiSimulationCandidate,
    choose_simulated_entry,
    evaluate_simulated_entry,
    reconfigure_simulation_portfolio,
)


def _candidate(
    *, score: str = "82", supportive: int = 3, adverse: int = 0, price: str = "10"
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
    assert allocation.quantity == Decimal("1900")
    assert allocation.amount == Decimal("19000")
    assert allocation.allocation_percent == Decimal("19")


def test_ai_simulation_allows_entry_when_only_factor_inputs_are_missing() -> None:
    allocation = choose_simulated_entry(
        AiSimulationCandidate(
            symbol="600519.SH",
            display_name="贵州茅台",
            score=Decimal("82"),
            last_price=Decimal("10"),
            supportive_factor_count=0,
            adverse_factor_count=0,
            available_factor_ids=(),
            unavailable_factor_ids=("return_on_equity", "news_sentiment"),
            rationale=("数据源暂未返回部分因子输入。",),
        ),
        available_cash=Decimal("100000"),
        initial_capital=Decimal("100000"),
        open_position_count=0,
        max_positions=3,
        max_position_percent=Decimal("25"),
        lot_size=Decimal("100"),
    )

    assert allocation is not None


def test_ai_simulation_does_not_treat_missing_factors_as_adverse_evidence() -> None:
    candidate = AiSimulationCandidate(
        symbol="600519.SH",
        display_name="贵州茅台",
        score=Decimal("82"),
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
    assert any("达到上限" in item for item in decision.blockers)
    assert not any("风险方向不占优" in item for item in decision.blockers)


def test_ai_simulation_allows_limited_adverse_evidence_when_support_is_stronger() -> None:
    decision = evaluate_simulated_entry(
        _candidate(score="76", supportive=3, adverse=1),
        available_cash=Decimal("100000"),
        initial_capital=Decimal("100000"),
        open_position_count=0,
        max_positions=3,
        max_position_percent=Decimal("25"),
        lot_size=Decimal("100"),
    )

    assert decision.allocation is not None


def test_ai_simulation_rejects_risk_dominant_factor_evidence() -> None:
    decision = evaluate_simulated_entry(
        _candidate(score="76", supportive=2, adverse=2),
        available_cash=Decimal("100000"),
        initial_capital=Decimal("100000"),
        open_position_count=0,
        max_positions=3,
        max_position_percent=Decimal("25"),
        lot_size=Decimal("100"),
    )

    assert decision.allocation is None
    assert any("风险方向不占优" in item for item in decision.blockers)


def test_reconfigure_simulation_portfolio_preserves_positions_and_applies_capital_delta() -> None:
    first_strategy_id = uuid4()
    second_strategy_id = uuid4()
    portfolio = AiSimulationPortfolio(
        portfolio_id=uuid4(),
        market="a_share",
        currency="CNY",
        initial_capital=Decimal("100000"),
        cash_balance=Decimal("75000"),
        max_positions=3,
    )

    updated = reconfigure_simulation_portfolio(
        portfolio,
        initial_capital=Decimal("120000"),
        max_positions=4,
        strategy_ids=(first_strategy_id, second_strategy_id),
        open_position_count=1,
    )

    assert updated.portfolio_id == portfolio.portfolio_id
    assert updated.initial_capital == Decimal("120000")
    assert updated.cash_balance == Decimal("95000")
    assert updated.max_positions == 4
    assert updated.strategy_ids == (first_strategy_id, second_strategy_id)


def test_reconfigure_simulation_portfolio_rejects_conflicting_open_positions() -> None:
    portfolio = AiSimulationPortfolio(
        portfolio_id=uuid4(),
        market="a_share",
        currency="CNY",
        initial_capital=Decimal("100000"),
        cash_balance=Decimal("25000"),
        max_positions=3,
    )

    try:
        reconfigure_simulation_portfolio(
            portfolio,
            initial_capital=Decimal("20000"),
            max_positions=1,
            strategy_ids=(),
            open_position_count=2,
        )
    except ValueError as error:
        assert "最多持仓" in str(error)
    else:
        raise AssertionError("expected conflicting account settings to be rejected")
