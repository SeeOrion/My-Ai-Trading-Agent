"""Hithink adapter for a single selected A-share's published financial detail."""

from __future__ import annotations

import asyncio
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

from ai_trading_agent.domain.aggregate.market import Instrument
from ai_trading_agent.domain.aggregate.watchlist_detail import (
    BalanceSheetSummary,
    CashFlowSummary,
    IncomeStatementSummary,
    TimeCatalyst,
    ValuationSummary,
    WatchlistFinancialDetail,
)
from ai_trading_agent.domain.enums.market import InstrumentType, Market
from ai_trading_agent.infrastructure.config.providers import HithinkFinanceSettings
from ai_trading_agent.infrastructure.rpc.hithink_client import (
    HithinkFinanceRestClient,
    HithinkFinanceServiceError,
    ResponseFetcher,
    date_from_milliseconds,
    datetime_from_milliseconds,
    decimal_or_none,
    response_items,
)


class HithinkWatchlistDetailProviderError(HithinkFinanceServiceError):
    """Raised when published A-share detail cannot be retrieved."""


class HithinkWatchlistDetailProvider:
    """Fetch bounded financial statements, valuation and disclosed event history."""

    name = "hithink_finance"

    def __init__(
        self, settings: HithinkFinanceSettings, *, response_fetcher: ResponseFetcher | None = None
    ) -> None:
        self._client = HithinkFinanceRestClient(settings, response_fetcher=response_fetcher)

    async def get_watchlist_financial_detail(
        self, instrument: Instrument
    ) -> WatchlistFinancialDetail:
        if (
            instrument.market is not Market.A_SHARE
            or instrument.instrument_type is not InstrumentType.EQUITY
        ):
            raise HithinkWatchlistDetailProviderError(
                "上市公司财报与 A 股估值详情仅适用于 A 股股票"
            )
        results = await asyncio.gather(
            self._optional(
                "/api/a-share/financials/income-statements",
                {"thscode": instrument.symbol, "period": "annual", "limit": 1},
            ),
            self._optional(
                "/api/a-share/financials/balance-sheets",
                {"thscode": instrument.symbol, "period": "annual", "limit": 1},
            ),
            self._optional(
                "/api/a-share/financials/cash-flow-statements",
                {"thscode": instrument.symbol, "period": "annual", "limit": 1},
            ),
            self._optional(
                "/api/a-share/valuations/snapshot",
                {"thscodes": instrument.symbol},
            ),
            self._optional(
                "/api/a-share/corporate-actions/adjustment-factors",
                {
                    "thscode": instrument.symbol,
                    "from": (date.today() - timedelta(days=730)).isoformat(),
                    "to": date.today().isoformat(),
                },
            ),
        )
        income_data, balance_data, cash_flow_data, valuation_data, actions_data = results
        notices: list[str] = []
        income = _income_summary(income_data, notices)
        balance = _balance_summary(balance_data, notices)
        cash_flow = _cash_flow_summary(cash_flow_data, notices)
        valuation = _valuation_summary(valuation_data, notices)
        catalysts = _time_catalysts(income, actions_data, notices)
        if not any((income, balance, cash_flow, valuation)):
            raise HithinkWatchlistDetailProviderError("未返回可展示的财务或估值数据")
        return WatchlistFinancialDetail(
            instrument=instrument,
            observed_at=datetime.now(UTC),
            source=self.name,
            income_statement=income,
            balance_sheet=balance,
            cash_flow=cash_flow,
            valuation=valuation,
            time_catalysts=tuple(catalysts),
            notices=tuple(notices),
        )

    async def _optional(
        self, path: str, parameters: dict[str, object]
    ) -> dict[str, object] | Exception:
        try:
            return await self._client.get(path, parameters)
        except HithinkFinanceServiceError as error:
            return error


def _income_summary(
    data: dict[str, object] | Exception, notices: list[str]
) -> IncomeStatementSummary | None:
    row = _first_row(data, "利润表", notices)
    if row is None:
        return None
    report_period = _date(row.get("period_end_ms"), "利润表报告期", notices)
    announced_on = _date(row.get("report_date_ms"), "利润表披露日", notices)
    if report_period is None or announced_on is None:
        return None
    return IncomeStatementSummary(
        report_period=report_period,
        announced_on=announced_on,
        currency=_text(row.get("currency")) or "CNY",
        operating_income=_decimal(row.get("operating_income"), "营业收入", notices),
        operating_profit=_decimal(row.get("operating_profit"), "营业利润", notices),
        net_profit=_decimal(row.get("net_profit"), "净利润", notices),
        basic_eps=_decimal(row.get("basic_eps"), "基本每股收益", notices),
    )


def _balance_summary(
    data: dict[str, object] | Exception, notices: list[str]
) -> BalanceSheetSummary | None:
    row = _first_row(data, "资产负债表", notices)
    if row is None:
        return None
    report_period = _date(row.get("period_end_ms"), "资产负债表报告期", notices)
    if report_period is None:
        return None
    assets = _decimal(row.get("assets_total"), "资产总计", notices)
    debt = _decimal(row.get("total_debt"), "负债合计", notices)
    debt_to_assets = (
        None if assets is None or assets == 0 or debt is None else debt / assets * Decimal("100")
    )
    return BalanceSheetSummary(
        report_period=report_period,
        currency=_text(row.get("currency")) or "CNY",
        total_assets=assets,
        total_debt=debt,
        total_equity=_decimal(row.get("holder_equity_total"), "所有者权益", notices),
        cash=_decimal(row.get("cash"), "货币资金", notices),
        accounts_receivable=_decimal(row.get("accounts_receivable"), "应收账款", notices),
        debt_to_assets_percent=debt_to_assets,
    )


def _cash_flow_summary(
    data: dict[str, object] | Exception, notices: list[str]
) -> CashFlowSummary | None:
    row = _first_row(data, "现金流量表", notices)
    if row is None:
        return None
    report_period = _date(row.get("period_end_ms"), "现金流报告期", notices)
    if report_period is None:
        return None
    return CashFlowSummary(
        report_period=report_period,
        currency=_text(row.get("currency")) or "CNY",
        operating_cash_flow=_decimal(row.get("act_cash_flow_net"), "经营现金流", notices),
        investing_cash_flow=_decimal(row.get("invest_cash_flow_net"), "投资现金流", notices),
        financing_cash_flow=_decimal(row.get("financing_cash_flow_net"), "筹资现金流", notices),
        net_cash_change=_decimal(row.get("cash_equivalents_net_addition"), "现金净增加额", notices),
    )


def _valuation_summary(
    data: dict[str, object] | Exception, notices: list[str]
) -> ValuationSummary | None:
    row = _first_row(data, "估值快照", notices)
    if row is None:
        return None
    timestamp = None
    if isinstance(data, dict):
        timestamp = _datetime(data.get("timestamp"), "估值时间", notices)
    return ValuationSummary(
        observed_at=timestamp,
        price_to_earnings_ttm=_decimal(row.get("pe_ttm"), "PE TTM", notices),
        price_to_earnings_mrq=_decimal(row.get("pe_mrq"), "PE MRQ", notices),
        price_to_book_mrq=_decimal(row.get("pb_mrq"), "PB MRQ", notices),
        price_to_sales_ttm=_decimal(row.get("ps_ttm"), "PS TTM", notices),
        price_to_cash_flow_ttm=_decimal(row.get("pcf_ttm"), "PCF TTM", notices),
    )


def _time_catalysts(
    income: IncomeStatementSummary | None,
    data: dict[str, object] | Exception,
    notices: list[str],
) -> list[TimeCatalyst]:
    catalysts: list[TimeCatalyst] = []
    if income is not None:
        catalysts.append(
            TimeCatalyst(
                occurred_on=income.announced_on,
                title="最近年度财报披露",
                detail=f"报告期截至 {income.report_period.isoformat()}（已披露事件，非未来预测）。",
                kind="financial_report",
            )
        )
    if isinstance(data, Exception):
        notices.append(f"除权除息事件暂不可用：{data}")
        return catalysts
    for row in response_items(data)[:6]:
        occurred_on = _date(row.get("ex_date_ms"), "除权除息日", notices)
        if occurred_on is None:
            continue
        dividend = _decimal(row.get("dividend_per_share"), "每股现金分红", notices)
        bonus = _decimal(row.get("per_share_bonus"), "每股送股", notices)
        details: list[str] = []
        if dividend is not None and dividend > 0:
            details.append(f"税前每股现金分红 {dividend}")
        if bonus is not None and bonus > 0:
            details.append(f"每股送股 {bonus}")
        if not details:
            continue
        catalysts.append(
            TimeCatalyst(
                occurred_on=occurred_on,
                title="已披露除权除息事件",
                detail="；".join(details) + "（历史事件，非未来安排）。",
                kind="corporate_action",
            )
        )
    return sorted(catalysts, key=lambda item: item.occurred_on, reverse=True)


def _first_row(
    data: dict[str, object] | Exception, label: str, notices: list[str]
) -> dict[str, object] | None:
    if isinstance(data, Exception):
        notices.append(f"{label}暂不可用：{data}")
        return None
    rows = response_items(data)
    if not rows:
        notices.append(f"{label}未返回已披露数据")
        return None
    return rows[0]


def _date(value: object, label: str, notices: list[str]) -> date | None:
    try:
        return date_from_milliseconds(value, label)
    except HithinkFinanceServiceError as error:
        notices.append(f"{label}格式异常：{error}")
        return None


def _datetime(value: object, label: str, notices: list[str]) -> datetime | None:
    try:
        return datetime_from_milliseconds(value, label)
    except HithinkFinanceServiceError as error:
        notices.append(f"{label}格式异常：{error}")
        return None


def _decimal(value: object, label: str, notices: list[str]) -> Decimal | None:
    try:
        return decimal_or_none(value, label)
    except HithinkFinanceServiceError as error:
        notices.append(f"{label}格式异常：{error}")
        return None


def _text(value: object) -> str | None:
    return value.strip() if isinstance(value, str) and value.strip() else None
