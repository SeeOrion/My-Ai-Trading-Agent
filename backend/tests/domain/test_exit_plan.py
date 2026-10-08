from dataclasses import replace
from datetime import UTC, datetime
from decimal import Decimal as D

from ai_trading_agent.domain.service.simulation_exit import (
    SimulationExitEvidence,
    evaluate_simulation_exit,
    review_exit_plan,
)

NOW = datetime(2026, 10, 8, 2, tzinfo=UTC)


def evidence(**changes):
    base = SimulationExitEvidence(D("100"), D("100"), D("1000"), D("100"), 0, D("100"))
    return replace(base, **changes)


def test_entry_plan_uses_atr_and_twice_initial_risk():
    plan = review_exit_plan(evidence(atr_14=D("3")), None, NOW)
    assert plan.stop_price == D("94")
    assert plan.target_price == D("112")


def test_review_never_loosens_stop_or_chases_profit_target():
    first = review_exit_plan(evidence(atr_14=D("2")), None, NOW)
    reviewed = review_exit_plan(evidence(atr_14=D("9")), first, NOW)
    assert reviewed.stop_price == first.stop_price == D("96")
    assert reviewed.target_price == first.target_price == D("108")


def test_missing_data_records_fallback_not_sell_signal():
    plan = review_exit_plan(evidence(), None, NOW, data_notes=("资金暂缺",))
    assert plan.stop_price == D("92")
    assert plan.target_price == D("116")
    assert plan.data_notes == ("资金暂缺",)
    decision = evaluate_simulation_exit(
        replace(evidence(), stop_price=plan.stop_price, target_price=plan.target_price)
    )
    assert decision.action == "hold"


def test_same_day_outflow_requires_multiple_technical_confirmations():
    adverse = evidence(
        factor_directions=(("momentum_20d", "adverse"), ("relative_volume_20d", "adverse"))
    )
    assert review_exit_plan(adverse, None, NOW).stop_price == D("92")
    assert review_exit_plan(adverse, None, NOW, fresh_flow_out=True).stop_price == D("97")
    repeated = evidence(factor_directions=(("momentum_20d", "adverse"),) * 2)
    assert review_exit_plan(repeated, None, NOW, fresh_flow_out=True).stop_price == D("92")


def test_recorded_target_is_used_instead_of_legacy_twenty_percent():
    decision = evaluate_simulation_exit(evidence(current_price=D("108"), target_price=D("108")))
    assert decision.action == "partial_exit"
    assert decision.quantity == D("500")


def test_rising_volatility_cannot_lower_existing_trailing_stop():
    decision = evaluate_simulation_exit(
        evidence(
            current_price=D("125"),
            highest_price=D("130"),
            profit_take_stage=1,
            atr_14=D("20"),
            previous_trailing_stop=D("124"),
        )
    )
    assert decision.trailing_stop_price == D("124")
    assert decision.action == "hold"
