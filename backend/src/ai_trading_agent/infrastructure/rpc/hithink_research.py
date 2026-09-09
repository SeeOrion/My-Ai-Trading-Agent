"""Hithink Finance adapter for published A-share financial facts."""

from __future__ import annotations

import asyncio
from datetime import date

from ai_trading_agent.domain.aggregate.market import Instrument
from ai_trading_agent.domain.aggregate.research import FinancialSnapshot
from ai_trading_agent.domain.enums.market import Market
from ai_trading_agent.infrastructure.config.providers import HithinkFinanceSettings
from ai_trading_agent.infrastructure.rpc.hithink_client import (
    HithinkFinanceRestClient,
    HithinkFinanceServiceError,
    ResponseFetcher,
    date_from_milliseconds,
    decimal_or_none,
    response_items,
)


class HithinkAshareResearchProviderError(HithinkFinanceServiceError):
    pass


class HithinkAshareResearchProvider:
    """Resolve the latest disclosed report before requesting its indicator block."""

    name = "hithink_finance"

    def __init__(
        self, settings: HithinkFinanceSettings, *, response_fetcher: ResponseFetcher | None = None
    ) -> None:
        self._client = HithinkFinanceRestClient(settings, response_fetcher=response_fetcher)

    async def get_financial_snapshot(self, instrument: Instrument) -> FinancialSnapshot:
        if instrument.market is not Market.A_SHARE:
            raise HithinkAshareResearchProviderError("Hithink financials only support A-share")
        return await asyncio.to_thread(self._get_financial_snapshot_sync, instrument)

    def _get_financial_snapshot_sync(self, instrument: Instrument) -> FinancialSnapshot:
        try:
            income = self._client.get_sync(
                "/api/a-share/financials/income-statements",
                {"thscode": instrument.symbol, "period": "annual", "limit": 1},
            )
            row = _first(income, instrument.symbol)
            year = int(row["fiscal_year"])
            indicators = self._client.get_sync(
                "/api/a-share/financials/indicators",
                {"thscode": instrument.symbol, "report": f"{year}-4"},
            )
        except (KeyError, TypeError, ValueError, HithinkFinanceServiceError) as error:
            raise HithinkAshareResearchProviderError(str(error)) from error
        values = _indicator_values(indicators)
        report_period = _required_date(row.get("period_end_ms"), "period_end_ms")
        announced_on = _required_date(row.get("report_date_ms"), "report_date_ms")
        return FinancialSnapshot(
            instrument=instrument,
            announced_on=max(announced_on, report_period),
            report_period=report_period,
            eps=decimal_or_none(row.get("basic_eps"), "basic_eps"),
            return_on_equity_pct=values.get("index_deduct_weighted_avg_roe"),
            gross_margin_pct=values.get("sale_gross_margin"),
            current_ratio=values.get("current_ratio"),
            # The financial endpoint has no documented net-profit-yoy field.
            net_profit_growth_pct=None,
            price_to_earnings=None,
            price_to_book=None,
            source=self.name,
        )


def _first(data: dict[str, object], symbol: str) -> dict[str, object]:
    rows = response_items(data)
    if not rows:
        raise HithinkAshareResearchProviderError(f"financial response omitted: {symbol}")
    return rows[0]


def _indicator_values(data: dict[str, object]) -> dict[str, object]:
    abilities = data.get("abilities")
    if not isinstance(abilities, list):
        raise HithinkAshareResearchProviderError("financial indicators omitted abilities")
    values: dict[str, object] = {}
    for ability in abilities:
        if not isinstance(ability, dict) or not isinstance(ability.get("indicators"), list):
            continue
        for indicator in ability["indicators"]:
            if isinstance(indicator, dict) and isinstance(indicator.get("index_id"), str):
                values[indicator["index_id"]] = indicator.get("value")
    return {
        key: decimal_or_none(values.get(key), key)
        for key in ("index_deduct_weighted_avg_roe", "sale_gross_margin", "current_ratio")
    }


def _required_date(value: object, field: str) -> date:
    result = date_from_milliseconds(value, field)
    if result is None:
        raise HithinkAshareResearchProviderError(f"financial response omitted {field}")
    return result
