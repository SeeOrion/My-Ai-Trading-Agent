from datetime import UTC, datetime
from decimal import Decimal

import pytest

from ai_trading_agent.infrastructure.rpc.tushare_market import (
    TushareProviderError,
    _decimal,
    _market_close,
)


def test_tushare_daily_observation_is_stamped_at_shanghai_close() -> None:
    assert _market_close("20260902") == datetime(2026, 9, 2, 7, 0, tzinfo=UTC)


def test_tushare_rejects_non_finite_provider_values() -> None:
    with pytest.raises(TushareProviderError, match="invalid close"):
        _decimal("NaN", "close")


def test_tushare_parses_decimal_values_without_float_rounding() -> None:
    assert _decimal("1.2300", "close") == Decimal("1.2300")
