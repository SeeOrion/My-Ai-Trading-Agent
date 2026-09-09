from __future__ import annotations

import json
from decimal import Decimal

import pytest

from ai_trading_agent.domain.aggregate.market import Instrument
from ai_trading_agent.domain.enums.market import InstrumentType, Market
from ai_trading_agent.infrastructure.config.providers import HithinkFinanceSettings
from ai_trading_agent.infrastructure.rpc.hithink_market import (
    HithinkFinanceMarketDataProvider,
    HithinkFinanceProviderError,
)


def _instrument() -> Instrument:
    return Instrument("600519.SH", Market.A_SHARE, InstrumentType.EQUITY)


@pytest.mark.asyncio
async def test_snapshot_maps_hithink_response_to_provider_neutral_quote() -> None:
    requested: list[tuple[str, str]] = []

    def response_fetcher(url: str, api_key: str, timeout_seconds: float) -> bytes:
        requested.append((url, api_key))
        assert timeout_seconds == 3
        return json.dumps(
            {
                "code": 0,
                "data": {
                    "item": [
                        {
                            "thscode": "600519.SH",
                            "last_price": "1330.00",
                            "open_price": "1320.00",
                            "high_price": "1342.00",
                            "low_price": "1318.00",
                            "prev_price": "1315.00",
                            "volume": "1000",
                        }
                    ]
                },
            }
        ).encode()

    provider = HithinkFinanceMarketDataProvider(
        HithinkFinanceSettings("test-key", timeout_seconds=3),
        response_fetcher=response_fetcher,
    )

    [quote] = await provider.get_latest_quotes([_instrument()])

    assert "thscodes=600519.SH" in requested[0][0]
    assert requested[0][1] == "test-key"
    assert quote.source == "hithink_finance"
    assert quote.last_price == Decimal("1330.00")
    assert quote.previous_close == Decimal("1315.00")


@pytest.mark.asyncio
async def test_snapshot_rejects_service_error() -> None:
    provider = HithinkFinanceMarketDataProvider(
        HithinkFinanceSettings("test-key"),
        response_fetcher=lambda *_: b'{"code": 401, "message": "invalid key"}',
    )

    with pytest.raises(HithinkFinanceProviderError, match="snapshot service error"):
        await provider.get_latest_quotes([_instrument()])
