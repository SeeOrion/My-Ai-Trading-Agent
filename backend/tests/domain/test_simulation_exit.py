from decimal import Decimal

from ai_trading_agent.domain.service.simulation_exit import (
    SimulationExitEvidence,
    evaluate_simulation_exit,
)


def _evidence(
    *,
    current: str = "100",
    cost: str = "100",
    quantity: str = "1000",
    highest: str = "100",
    stage: int = 0,
    atr: str | None = None,
    sma: str | None = None,
    factors: tuple[tuple[str, str], ...] = (),
) -> SimulationExitEvidence:
    return SimulationExitEvidence(
        current_price=Decimal(current),
        average_cost=Decimal(cost),
        quantity=Decimal(quantity),
        highest_price=Decimal(highest),
        profit_take_stage=stage,
        lot_size=Decimal("100"),
        atr_14=None if atr is None else Decimal(atr),
        sma_20=None if sma is None else Decimal(sma),
        factor_directions=factors,
    )


def test_hard_stop_closes_the_full_position_at_eight_percent_loss() -> None:
    decision = evaluate_simulation_exit(_evidence(current="92"))

    assert decision.action == "full_exit"
    assert decision.quantity == Decimal("1000")
    assert decision.reason_code == "hard_stop_loss"


def test_first_profit_target_sells_half_and_activates_atr_protection() -> None:
    decision = evaluate_simulation_exit(
        _evidence(current="120", highest="118", atr="2")
    )

    assert decision.action == "partial_exit"
    assert decision.quantity == Decimal("500")
    assert decision.reason_code == "first_profit_target"
    assert decision.profit_take_stage == 1
    assert decision.trailing_stop_price == Decimal("114.00")


def test_small_position_is_fully_sold_at_the_first_profit_target() -> None:
    decision = evaluate_simulation_exit(
        _evidence(current="120", quantity="100", atr="2")
    )

    assert decision.action == "full_exit"
    assert decision.quantity == Decimal("100")


def test_atr_trailing_stop_protects_the_remaining_position() -> None:
    decision = evaluate_simulation_exit(
        _evidence(current="119", highest="130", stage=1, atr="5")
    )

    assert decision.action == "full_exit"
    assert decision.reason_code == "trailing_profit_stop"
    assert decision.trailing_stop_price == Decimal("120.0")


def test_trend_exit_requires_price_break_and_two_adverse_confirmations() -> None:
    decision = evaluate_simulation_exit(
        _evidence(
            current="95",
            sma="100",
            factors=(
                ("momentum_20d", "adverse"),
                ("moving_average_trend", "adverse"),
            ),
        )
    )

    assert decision.action == "full_exit"
    assert decision.reason_code == "confirmed_trend_breakdown"


def test_missing_optional_evidence_does_not_become_a_sell_signal() -> None:
    decision = evaluate_simulation_exit(_evidence(current="101"))

    assert decision.action == "hold"
    assert decision.quantity == Decimal("0")
    assert decision.highest_price == Decimal("101")
