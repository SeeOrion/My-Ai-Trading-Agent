from __future__ import annotations

import json

import pytest

from ai_trading_agent.domain.aggregate.market import Instrument
from ai_trading_agent.domain.enums.market import Market
from ai_trading_agent.infrastructure.config.providers import HithinkFinanceSettings
from ai_trading_agent.infrastructure.rpc.hithink_instruments import (
    HithinkInstrumentIdentityProvider,
)


@pytest.mark.asyncio
async def test_a_share_code_resolves_to_its_verified_display_name() -> None:
    requests: list[str] = []

    def response_fetcher(url: str, api_key: str, timeout_seconds: float) -> bytes:
        requests.append(url)
        assert api_key == "test-key"
        assert timeout_seconds == 3
        return json.dumps(
            {
                "code": 0,
                "data": {
                    "item": [
                        {
                            "thscode": "600737.SH",
                            "ticker": "600737",
                            "name": "中粮糖业",
                            "asset_type": "a-share",
                        }
                    ]
                },
            }
        ).encode()

    provider = HithinkInstrumentIdentityProvider(
        HithinkFinanceSettings("test-key", timeout_seconds=3), response_fetcher=response_fetcher
    )
    identity = await provider.resolve(Instrument("600737", Market.A_SHARE))

    assert identity is not None
    assert identity.instrument.symbol == "600737.SH"
    assert identity.display_name == "中粮糖业"
    assert "asset_type=a-share" in requests[0]


@pytest.mark.asyncio
async def test_hong_kong_identity_does_not_call_a_share_or_fund_catalogue() -> None:
    provider = HithinkInstrumentIdentityProvider(
        HithinkFinanceSettings("test-key"),
        response_fetcher=lambda *_: pytest.fail("unsupported market must not call upstream"),
    )

    identity = await provider.resolve(Instrument("00700", Market.HONG_KONG))

    assert identity is None
