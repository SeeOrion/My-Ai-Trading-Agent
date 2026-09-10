from __future__ import annotations

import json
from decimal import Decimal

import pytest

from ai_trading_agent.infrastructure.config.providers import HithinkFinanceSettings
from ai_trading_agent.infrastructure.rpc.hithink_market_brief import HithinkMarketBriefProvider


@pytest.mark.asyncio
async def test_market_brief_maps_benchmarks_and_ranks_industries() -> None:
    def response_fetcher(url: str, api_key: str, timeout_seconds: float) -> bytes:
        assert api_key == "test-key"
        assert timeout_seconds == 3
        if "ths-index-list" in url:
            return json.dumps(
                {
                    "code": 0,
                    "data": {
                        "timestamp": 1_700_000_000_000,
                        "item": [
                            {"thscode": "886001.TI", "name": "电子"},
                            {"thscode": "886002.TI", "name": "银行"},
                            {"thscode": "886003.TI", "name": "医药"},
                        ],
                    },
                }
            ).encode()
        requested = url.split("thscodes=", maxsplit=1)[1].split("&", maxsplit=1)[0]
        rows = []
        for symbol in requested.split("%2C"):
            values = {
                "000001.SH": ("3000", "10", "0.33"),
                "399001.SZ": ("9000", "-20", "-0.22"),
                "399006.SZ": ("1800", "5", "0.28"),
                "000300.SH": ("3500", "1", "0.03"),
                "886001.TI": ("1200", "0", "2.1"),
                "886002.TI": ("900", "0", "-1.4"),
                "886003.TI": ("1100", "0", "0.6"),
            }[symbol]
            rows.append(
                {
                    "thscode": symbol,
                    "last_price": values[0],
                    "price_change": values[1],
                    "price_change_ratio_pct": values[2],
                }
            )
        return json.dumps({"code": 0, "data": {"item": rows}}).encode()

    brief = await HithinkMarketBriefProvider(
        HithinkFinanceSettings("test-key", timeout_seconds=3), response_fetcher=response_fetcher
    ).get_post_market_brief()

    assert brief.source == "hithink_finance_index"
    assert [item.name for item in brief.indices] == ["上证综指", "深证成指", "创业板指", "沪深 300"]
    assert brief.indices[0].last_price == Decimal("3000")
    assert [item.name for item in brief.leading_sectors] == ["电子", "医药", "银行"]
    assert [item.name for item in brief.lagging_sectors] == ["银行", "医药", "电子"]
