"""Hithink Finance adapters for selected public funds and exchange-traded ETFs."""

from __future__ import annotations

import asyncio
from collections.abc import Iterable
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from ai_trading_agent.domain.aggregate.fund import (
    FundAllocation,
    FundHolding,
    FundNavPoint,
    FundNews,
    FundOverview,
    FundResearchReport,
)
from ai_trading_agent.domain.aggregate.market import Instrument, Quote
from ai_trading_agent.domain.aggregate.technical import PriceBar
from ai_trading_agent.domain.enums.market import InstrumentType, Market
from ai_trading_agent.infrastructure.config.providers import HithinkFinanceSettings
from ai_trading_agent.infrastructure.rpc.hithink_client import (
    HithinkFinanceRestClient,
    HithinkFinanceServiceError,
    ResponseFetcher,
    date_from_milliseconds,
    datetime_from_milliseconds,
    decimal_or_none,
    non_negative_decimal,
    response_items,
)


class HithinkFundProviderError(HithinkFinanceServiceError):
    """A selected fund cannot be served by the documented fund endpoints."""


class HithinkFundMarketDataProvider:
    """Use market price for ETFs and published NAV for selected OTC funds."""

    name = "hithink_finance_fund"

    def __init__(
        self, settings: HithinkFinanceSettings, *, response_fetcher: ResponseFetcher | None = None
    ) -> None:
        self._client = HithinkFinanceRestClient(settings, response_fetcher=response_fetcher)

    def supports(self, market: Market) -> bool:
        return market in {Market.A_SHARE, Market.FUND}

    async def get_latest_quotes(self, instruments: Iterable[Instrument]) -> list[Quote]:
        requested = list(instruments)
        if not all(_is_supported(item) for item in requested):
            raise HithinkFundProviderError(
                "fund adapter supports selected OTC funds and A-share ETFs"
            )
        return [await self._quote(instrument) for instrument in requested]

    async def _quote(self, instrument: Instrument) -> Quote:
        try:
            if _is_exchange_etf(instrument):
                data = await self._client.get(
                    "/api/fund/market/snapshot", {"thscode": instrument.symbol}
                )
                row = _first_item(data, instrument.symbol)
                return Quote(
                    instrument=instrument,
                    last_price=non_negative_decimal(row.get("last_price"), "last_price"),
                    observed_at=datetime.now(UTC),
                    source=self.name,
                    open_price=decimal_or_none(row.get("open_price"), "open_price"),
                    high_price=decimal_or_none(row.get("high_price"), "high_price"),
                    low_price=decimal_or_none(row.get("low_price"), "low_price"),
                    previous_close=decimal_or_none(row.get("prev_price"), "prev_price"),
                    volume=decimal_or_none(row.get("volume"), "volume"),
                )
            data = await self._client.get(
                "/api/fund/profile/detail", {"thscode": instrument.symbol}
            )
            row = _first_item(data, instrument.symbol)
            nav = non_negative_decimal(row.get("unit_nav"), "unit_nav")
            return Quote(
                instrument=instrument,
                last_price=nav,
                observed_at=datetime.now(UTC),
                source="hithink_finance_fund_nav",
            )
        except HithinkFinanceServiceError as error:
            raise HithinkFundProviderError(str(error)) from error


class HithinkFundHistoricalBarsProvider:
    """True OHLCV is available only for exchange-traded ETFs, never OTC NAVs."""

    name = "hithink_finance_fund"

    def __init__(
        self, settings: HithinkFinanceSettings, *, response_fetcher: ResponseFetcher | None = None
    ) -> None:
        self._client = HithinkFinanceRestClient(settings, response_fetcher=response_fetcher)

    async def get_daily_bars(self, instrument: Instrument, limit: int) -> tuple[PriceBar, ...]:
        if not _is_exchange_etf(instrument):
            raise HithinkFundProviderError(
                "场外基金只有净值序列，没有真实 OHLCV；不能生成 K 线或成交量分布"
            )
        end = datetime.now(UTC)
        start = end - timedelta(days=limit * 3)
        try:
            data = await self._client.get(
                "/api/fund/market/historical",
                {
                    "thscode": instrument.symbol,
                    "interval": "1d",
                    "start": int(start.timestamp() * 1000),
                    "end": int(end.timestamp() * 1000),
                },
            )
        except HithinkFinanceServiceError as error:
            raise HithinkFundProviderError(str(error)) from error
        bars = tuple(_bar(instrument, row) for row in response_items(data))
        if not bars:
            raise HithinkFundProviderError(f"no ETF daily bars for {instrument.symbol}")
        return tuple(sorted(bars, key=lambda item: item.session_date)[-limit:])


class HithinkFundResearchProvider:
    """Compose disclosed fund research sections without inventing missing values."""

    name = "hithink_finance_fund"

    def __init__(
        self, settings: HithinkFinanceSettings, *, response_fetcher: ResponseFetcher | None = None
    ) -> None:
        self._client = HithinkFinanceRestClient(settings, response_fetcher=response_fetcher)

    async def get_fund_research(self, instrument: Instrument) -> FundResearchReport:
        if not _is_supported(instrument):
            raise HithinkFundProviderError(
                "fund research supports selected OTC funds and A-share ETFs"
            )
        return await asyncio.to_thread(self._get_fund_research_sync, instrument)

    def _get_fund_research_sync(self, instrument: Instrument) -> FundResearchReport:
        limitations = [
            "持仓、资产配置、持有人和财务指标均为定期披露口径，不代表实时组合或资金流。",
            "基金资讯为标题与摘要元数据；是否可访问原文取决于返回链接及授权。",
        ]
        profile_data = self._required("/api/fund/profile/detail", {"thscode": instrument.symbol})
        profile_row = _first_item(profile_data, instrument.symbol)
        optional = self._optional_sections(instrument.symbol, limitations)
        return FundResearchReport(
            instrument=instrument,
            observed_at=datetime.now(UTC),
            source=self.name,
            overview=FundOverview(
                name=_text(profile_row.get("fund_name")),
                management_company=_text(profile_row.get("mgmt_name")),
                manager_name=_text(profile_row.get("manager_name")),
                fund_scale=decimal_or_none(profile_row.get("fund_scale"), "fund_scale"),
                latest_unit_nav=decimal_or_none(profile_row.get("unit_nav"), "unit_nav"),
            ),
            nav_history=tuple(_nav_point(row) for row in response_items(optional["nav"])),
            returns_percent=_period_values(response_items(optional["returns"])),
            drawdowns_percent=_period_values(response_items(optional["drawdowns"])),
            holdings=tuple(_holding(row) for row in response_items(optional["holdings"])),
            allocations=tuple(_allocation(row) for row in response_items(optional["allocation"])),
            institutional_holding_percent=_holder_percent(optional["holders"]),
            latest_financials=_latest_financials(optional["financials"]),
            diagnostics=_diagnostics(optional["diagnostics"]),
            news=tuple(_news(row) for row in response_items(optional["news"])),
            limitations=tuple(limitations),
        )

    def _required(self, path: str, parameters: dict[str, object]) -> dict[str, object]:
        try:
            return self._client.get_sync(path, parameters)
        except HithinkFinanceServiceError as error:
            raise HithinkFundProviderError(str(error)) from error

    def _optional_sections(
        self, thscode: str, limitations: list[str]
    ) -> dict[str, dict[str, object]]:
        requests = {
            "nav": (
                "/api/fund/performance/nav",
                {"thscode": thscode, "range": "year", "nav_type": "unit,adj"},
            ),
            "returns": ("/api/fund/performance/returns", {"thscode": thscode}),
            "drawdowns": ("/api/fund/performance/drawdowns", {"thscode": thscode}),
            "holdings": ("/api/fund/portfolio/holdings", {"thscode": thscode}),
            "allocation": ("/api/fund/portfolio/asset-allocation", {"thscode": thscode}),
            "holders": ("/api/fund/holders/detail", {"thscode": thscode, "merge_scope": "all"}),
            "financials": ("/api/fund/financials/indicators", {"thscode": thscode}),
            "diagnostics": ("/api/fund/diagnostics/detail", {"thscode": thscode}),
            "news": ("/api/fund/news/article-list", {"thscode": thscode, "limit": 8}),
        }
        results: dict[str, dict[str, object]] = {}
        for name, (path, parameters) in requests.items():
            try:
                results[name] = self._client.get_sync(path, parameters)
            except HithinkFinanceServiceError as error:
                results[name] = {}
                limitations.append(f"{name} 数据暂不可用：{error}")
        return results


def _is_exchange_etf(instrument: Instrument) -> bool:
    return instrument.market is Market.A_SHARE and instrument.instrument_type is InstrumentType.ETF


def _is_supported(instrument: Instrument) -> bool:
    return _is_exchange_etf(instrument) or (
        instrument.market is Market.FUND and instrument.instrument_type is InstrumentType.FUND
    )


def _first_item(data: dict[str, object], thscode: str) -> dict[str, object]:
    rows = response_items(data)
    if not rows:
        raise HithinkFundProviderError(f"fund response omitted: {thscode}")
    return rows[0]


def _bar(instrument: Instrument, row: dict[str, object]) -> PriceBar:
    session_date = date_from_milliseconds(row.get("date_ms"), "date_ms")
    if session_date is None:
        raise HithinkFundProviderError("ETF bar omitted date_ms")
    return PriceBar(
        instrument=instrument,
        session_date=session_date,
        open_price=non_negative_decimal(row.get("open_price"), "open_price"),
        high_price=non_negative_decimal(row.get("high_price"), "high_price"),
        low_price=non_negative_decimal(row.get("low_price"), "low_price"),
        close_price=non_negative_decimal(row.get("close_price"), "close_price"),
        volume=non_negative_decimal(row.get("volume"), "volume"),
    )


def _nav_point(row: dict[str, object]) -> FundNavPoint:
    nav_date = date_from_milliseconds(row.get("nav_date"), "nav_date")
    if nav_date is None:
        raise HithinkFundProviderError("NAV point omitted nav_date")
    return FundNavPoint(
        nav_date=nav_date,
        unit_nav=decimal_or_none(row.get("unit_nav"), "unit_nav"),
        adjusted_nav=decimal_or_none(row.get("adj_nav"), "adj_nav"),
    )


def _holding(row: dict[str, object]) -> FundHolding:
    return FundHolding(
        name=_text(row.get("stock_name")) or _text(row.get("name")) or "未披露名称",
        asset_type=_text(row.get("asset_type")),
        weight_percent=decimal_or_none(row.get("hold_ratio"), "hold_ratio"),
        market_value=decimal_or_none(row.get("position_capital"), "position_capital"),
        disclosed_at=date_from_milliseconds(row.get("publish_date_ms"), "publish_date_ms"),
    )


def _allocation(row: dict[str, object]) -> FundAllocation:
    return FundAllocation(
        report_date=date_from_milliseconds(row.get("report_date_ms"), "report_date_ms"),
        stock_percent=decimal_or_none(row.get("stock_ratio_pct"), "stock_ratio_pct"),
        bond_percent=decimal_or_none(row.get("bond_ratio_pct"), "bond_ratio_pct"),
        cash_percent=decimal_or_none(row.get("deposit_ratio_pct"), "deposit_ratio_pct"),
        other_percent=decimal_or_none(row.get("other_ratio_pct"), "other_ratio_pct"),
    )


def _period_values(rows: list[dict[str, object]]) -> dict[str, Decimal | None]:
    row = rows[0] if rows else {}
    return {
        key: decimal_or_none(row.get(key), key)
        for key in (
            "week",
            "month",
            "tmonth",
            "hyear",
            "year",
            "twoyear",
            "tyear",
            "fyear",
            "nowyear",
            "now",
        )
        if key in row
    } | {
        key: decimal_or_none(row.get(key), key)
        for key in (
            "return_week",
            "return_month",
            "return_tmonth",
            "return_hyear",
            "return_year",
            "return_tyear",
            "return_fyear",
            "return_nowyear",
            "return_now",
        )
        if key in row
    }


def _holder_percent(data: dict[str, object]) -> Decimal | None:
    rows = response_items(data)
    return decimal_or_none(rows[0].get("ins_position"), "ins_position") if rows else None


def _latest_financials(data: dict[str, object]) -> dict[str, Decimal | None]:
    rows = response_items(data)
    row = rows[0] if rows else {}
    fields = ("asset_nav", "current_profit", "current_income", "distribution_profit", "nav_rate")
    return {field: decimal_or_none(row.get(field), field) for field in fields if field in row}


def _diagnostics(data: dict[str, object]) -> dict[str, object]:
    rows = response_items(data)
    if not rows:
        return {}
    row = rows[0]
    return {
        key: row[key]
        for key in ("fund_type", "dimensions", "probabilities", "resilience")
        if key in row
    }


def _news(row: dict[str, object]) -> FundNews:
    return FundNews(
        title=_text(row.get("title")) or "未命名基金资讯",
        summary=_text(row.get("summary")),
        publisher=_text(row.get("source")),
        url=_text(row.get("url")),
        published_at=datetime_from_milliseconds(row.get("publish_time_ms"), "publish_time_ms"),
    )


def _text(value: object) -> str | None:
    text = str(value).strip() if value is not None else ""
    return text or None
