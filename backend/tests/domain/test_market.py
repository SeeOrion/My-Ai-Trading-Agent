from datetime import datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

import pytest

from ai_trading_agent.domain.aggregate.market import Instrument, Quote
from ai_trading_agent.domain.enums.market import InstrumentType, Market


def test_instrument_normalizes_identity_and_market_currency() -> None:
    instrument = Instrument("  0700.hk ", Market.HONG_KONG, InstrumentType.EQUITY)

    assert instrument.symbol == "0700.HK"
    assert instrument.currency == "HKD"


def test_quote_rejects_naive_timestamp() -> None:
    instrument = Instrument("AAPL", Market.UNITED_STATES)

    with pytest.raises(ValueError, match="timezone-aware"):
        Quote(
            instrument=instrument,
            last_price=Decimal("200"),
            observed_at=datetime(2026, 9, 2, 12, 0),
            source="fixture",
        )


def test_quote_normalizes_source_and_time_to_utc() -> None:
    instrument = Instrument("510300.SH", Market.A_SHARE, InstrumentType.ETF)
    quote = Quote(
        instrument=instrument,
        last_price=Decimal("4.12"),
        observed_at=datetime(2026, 9, 2, 20, 0, tzinfo=ZoneInfo("Asia/Shanghai")),
        source="  Futu  ",
    )

    assert quote.source == "futu"
    assert quote.observed_at == datetime(2026, 9, 2, 12, 0, tzinfo=ZoneInfo("UTC"))
