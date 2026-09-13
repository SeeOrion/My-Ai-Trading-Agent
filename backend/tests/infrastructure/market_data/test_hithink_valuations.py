from __future__ import annotations

import json
from decimal import Decimal

import pytest

from ai_trading_agent.domain.aggregate.market import Instrument
from ai_trading_agent.domain.enums.market import Market
from ai_trading_agent.infrastructure.config.providers import HithinkFinanceSettings
from ai_trading_agent.infrastructure.rpc.hithink_valuations import HithinkAshareValuationProvider


@pytest.mark.asyncio
async def test_factor_valuation_adapter_uses_the_small_snapshot_endpoint() -> None:
    requested: list[str] = []

    def response_fetcher(url: str, _api_key: str, _timeout_seconds: float) -> bytes:
        requested.append(url)
        return json.dumps(
            {
                "code": 0,
                "data": {"item": [{"pe_ttm": "20", "pb_mrq": "2.5"}]},
            }
        ).encode()

    provider = HithinkAshareValuationProvider(
        HithinkFinanceSettings("test-key"), response_fetcher=response_fetcher
    )

    snapshot = await provider.get_valuation_snapshot(Instrument("600519.SH", Market.A_SHARE))

    assert requested == [
        "https://fuyao.aicubes.cn/api/a-share/valuations/snapshot?thscodes=600519.SH"
    ]
    assert snapshot.pe_ttm == Decimal("20")
    assert snapshot.pb_mrq == Decimal("2.5")
