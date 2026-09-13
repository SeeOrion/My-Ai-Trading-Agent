from datetime import date
from decimal import Decimal

import pytest

from ai_trading_agent.domain.ability.factors import (
    DEFAULT_FACTOR_REGISTRY,
    FactorMetadata,
    FactorReturnPair,
    calculate_factor_diagnostics,
)
from ai_trading_agent.domain.aggregate.market import Instrument
from ai_trading_agent.domain.enums.market import Market


def test_default_factor_registry_has_explicit_input_contracts() -> None:
    factor = DEFAULT_FACTOR_REGISTRY.get("return_on_equity")

    assert factor.columns_required == ("fund:roe_pct",)
    assert factor.formula == "fund:roe_pct"
    assert len(DEFAULT_FACTOR_REGISTRY.list()) == 10
    assert DEFAULT_FACTOR_REGISTRY.get("book_to_price").columns_required == ("fund:pb_mrq",)


def test_factor_metadata_rejects_implicit_unknown_inputs() -> None:
    with pytest.raises(ValueError, match="unsupported input columns"):
        FactorMetadata("bad", "Bad", "test", "x", ("secret",), 0, 1, "Bad input")


def test_factor_diagnostics_use_only_future_returns_and_date_cross_sections() -> None:
    pairs = tuple(
        FactorReturnPair(
            Instrument(f"S{index}", Market.UNITED_STATES),
            date(2026, 9, 1),
            date(2026, 9, 2),
            Decimal(index),
            Decimal(index),
        )
        for index in range(1, 6)
    )

    diagnostics = calculate_factor_diagnostics(pairs)

    assert diagnostics.information_coefficient == Decimal("1")
    assert diagnostics.information_ratio is None


def test_factor_return_pair_rejects_same_day_return() -> None:
    with pytest.raises(ValueError, match="avoid look-ahead"):
        FactorReturnPair(
            Instrument("AAPL", Market.UNITED_STATES),
            date(2026, 9, 1),
            date(2026, 9, 1),
            Decimal("1"),
            Decimal("0.01"),
        )
