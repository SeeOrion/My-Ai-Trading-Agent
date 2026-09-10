from __future__ import annotations

import json
from decimal import Decimal

import pytest

from ai_trading_agent.domain.aggregate.market import Instrument
from ai_trading_agent.domain.enums.market import InstrumentType, Market
from ai_trading_agent.infrastructure.config.providers import HithinkFinanceSettings
from ai_trading_agent.infrastructure.rpc.hithink_watchlist_detail import (
    HithinkWatchlistDetailProvider,
)


@pytest.mark.asyncio
async def test_selected_a_share_detail_maps_published_financial_sections() -> None:
    requested: list[str] = []

    def response_fetcher(url: str, _api_key: str, _timeout_seconds: float) -> bytes:
        requested.append(url)
        payload = {"code": 0, "data": {"item": []}}
        if "income-statements" in url:
            payload["data"]["item"] = [
                {
                    "period_end_ms": 1735603200000,
                    "report_date_ms": 1741996800000,
                    "currency": "CNY",
                    "operating_income": "1000",
                    "operating_profit": "350",
                    "net_profit": "280",
                    "basic_eps": "2.8",
                }
            ]
        elif "balance-sheets" in url:
            payload["data"]["item"] = [
                {
                    "period_end_ms": 1735603200000,
                    "currency": "CNY",
                    "assets_total": "2000",
                    "total_debt": "500",
                    "holder_equity_total": "1500",
                    "cash": "400",
                    "accounts_receivable": "120",
                }
            ]
        elif "cash-flow-statements" in url:
            payload["data"]["item"] = [
                {
                    "period_end_ms": 1735603200000,
                    "currency": "CNY",
                    "act_cash_flow_net": "420",
                    "invest_cash_flow_net": "-160",
                    "financing_cash_flow_net": "-90",
                    "cash_equivalents_net_addition": "170",
                }
            ]
        elif "valuations/snapshot" in url:
            payload["data"] = {
                "timestamp": 1756684800000,
                "item": [
                    {
                        "pe_ttm": "20.5",
                        "pe_mrq": "21.1",
                        "pb_mrq": "3.2",
                        "ps_ttm": "4.1",
                        "pcf_ttm": "18.4",
                    }
                ],
            }
        elif "adjustment-factors" in url:
            payload["data"]["item"] = [
                {"ex_date_ms": 1747267200000, "dividend_per_share": "1.2", "per_share_bonus": "0"}
            ]
        return json.dumps(payload).encode()

    provider = HithinkWatchlistDetailProvider(
        HithinkFinanceSettings("test-key"), response_fetcher=response_fetcher
    )

    detail = await provider.get_watchlist_financial_detail(
        Instrument("600519.SH", Market.A_SHARE, InstrumentType.EQUITY)
    )

    assert len(requested) == 5
    assert detail.income_statement is not None
    assert detail.income_statement.net_profit == Decimal("280")
    assert detail.balance_sheet is not None
    assert detail.balance_sheet.debt_to_assets_percent == Decimal("25.00")
    assert detail.cash_flow is not None
    assert detail.cash_flow.operating_cash_flow == Decimal("420")
    assert detail.valuation is not None
    assert detail.valuation.price_to_earnings_ttm == Decimal("20.5")
    assert detail.time_catalysts[0].title == "已披露除权除息事件"
