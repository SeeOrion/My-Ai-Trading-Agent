from __future__ import annotations

import json
from decimal import Decimal

import pytest

from ai_trading_agent.domain.aggregate.market import Instrument
from ai_trading_agent.domain.enums.market import InstrumentType, Market
from ai_trading_agent.infrastructure.config.providers import HithinkFinanceSettings
from ai_trading_agent.infrastructure.rpc.hithink_funds import (
    HithinkFundHistoricalBarsProvider,
    HithinkFundMarketDataProvider,
)


def _etf() -> Instrument:
    return Instrument("510300.SH", Market.A_SHARE, InstrumentType.ETF)


@pytest.mark.asyncio
async def test_etf_snapshot_maps_exchange_fund_fields_to_quote() -> None:
    provider = HithinkFundMarketDataProvider(
        HithinkFinanceSettings("test-key"),
        response_fetcher=lambda *_: json.dumps(
            {
                "code": 0,
                "data": {
                    "item": [
                        {
                            "thscode": "510300.SH",
                            "last_price": "4.15",
                            "prev_price": "4.10",
                            "volume": "12000",
                        }
                    ]
                },
            }
        ).encode(),
    )

    [quote] = await provider.get_latest_quotes([_etf()])

    assert quote.source == "hithink_finance_fund"
    assert quote.last_price == Decimal("4.15")
    assert quote.previous_close == Decimal("4.10")


@pytest.mark.asyncio
async def test_etf_history_maps_documented_ohlcv_fields_to_price_bars() -> None:
    provider = HithinkFundHistoricalBarsProvider(
        HithinkFinanceSettings("test-key"),
        response_fetcher=lambda *_: json.dumps(
            {
                "code": 0,
                "data": {
                    "item": [
                        {
                            "date_ms": 1735689600000,
                            "open_price": "4.00",
                            "high_price": "4.20",
                            "low_price": "3.95",
                            "close_price": "4.15",
                            "volume": "12000",
                        }
                    ]
                },
            }
        ).encode(),
    )

    [bar] = await provider.get_daily_bars(_etf(), limit=60)

    assert bar.close_price == Decimal("4.15")
    assert bar.volume == Decimal("12000")
