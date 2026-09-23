from datetime import UTC, datetime

import pytest

from ai_trading_agent.domain.aggregate.market import Instrument
from ai_trading_agent.domain.enums.market import InstrumentType, Market
from ai_trading_agent.infrastructure.config.providers import FutuSettings
from ai_trading_agent.infrastructure.rpc.futu_market import (
    FutuMarketDataProvider,
    FutuProviderError,
    FutuSymbolMapper,
    _parse_futu_observed_at,
)
from ai_trading_agent.infrastructure.rpc.historical_bars import (
    FutuHistoricalBarsProvider,
    HistoricalBarsProviderError,
)


@pytest.mark.parametrize(
    ("instrument", "expected"),
    [
        (Instrument("600519.SH", Market.A_SHARE), "SH.600519"),
        (Instrument("700.HK", Market.HONG_KONG), "HK.00700"),
        (Instrument("AAPL", Market.UNITED_STATES), "US.AAPL"),
    ],
)
def test_maps_canonical_symbols_to_futu_codes(instrument: Instrument, expected: str) -> None:
    assert FutuSymbolMapper.to_provider_code(instrument) == expected


def test_option_requires_explicit_futu_contract_code() -> None:
    instrument = Instrument("AAPL", Market.UNITED_STATES, InstrumentType.OPTION)

    with pytest.raises(ValueError, match="explicit Futu"):
        FutuSymbolMapper.to_provider_code(instrument)


@pytest.mark.parametrize(
    ("code", "market", "expected"),
    [
        ("HK.00700", Market.HONG_KONG, "00700"),
        ("US.AAPL", Market.UNITED_STATES, "AAPL"),
        ("SH.600519", Market.A_SHARE, "600519.SH"),
    ],
)
def test_maps_futu_snapshot_code_back_to_canonical_symbol(
    code: str, market: Market, expected: str
) -> None:
    assert FutuSymbolMapper.from_provider_code(code, market).symbol == expected


def test_us_quote_timestamp_is_normalized_to_utc() -> None:
    parsed = _parse_futu_observed_at("2026-09-02", "09:30:00", Market.UNITED_STATES)

    assert parsed == datetime(2026, 9, 2, 13, 30, tzinfo=UTC)


def test_futu_rejects_an_unreachable_opend_gateway(monkeypatch: pytest.MonkeyPatch) -> None:
    def refused(*args: object, **kwargs: object) -> None:
        raise ConnectionRefusedError("refused")

    monkeypatch.setattr("socket.create_connection", refused)
    provider = FutuMarketDataProvider(FutuSettings())

    with pytest.raises(FutuProviderError, match="OpenD is unreachable"):
        provider._ensure_gateway_is_reachable()


def test_futu_historical_bars_fail_fast_before_sdk_reconnects(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def refused(*args: object, **kwargs: object) -> None:
        raise ConnectionRefusedError("refused")

    monkeypatch.setattr("socket.create_connection", refused)
    provider = FutuHistoricalBarsProvider(FutuSettings())

    with pytest.raises(HistoricalBarsProviderError, match="OpenD is unreachable"):
        provider._get_daily_bars_sync(Instrument("AAPL", Market.UNITED_STATES), limit=20)
