"""Focused, source-attributed financial detail for one watchlist instrument."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal

from ai_trading_agent.domain.aggregate.market import Instrument


@dataclass(frozen=True, slots=True)
class IncomeStatementSummary:
    report_period: date
    announced_on: date
    currency: str
    operating_income: Decimal | None
    operating_profit: Decimal | None
    net_profit: Decimal | None
    basic_eps: Decimal | None


@dataclass(frozen=True, slots=True)
class BalanceSheetSummary:
    report_period: date
    currency: str
    total_assets: Decimal | None
    total_debt: Decimal | None
    total_equity: Decimal | None
    cash: Decimal | None
    accounts_receivable: Decimal | None
    debt_to_assets_percent: Decimal | None


@dataclass(frozen=True, slots=True)
class CashFlowSummary:
    report_period: date
    currency: str
    operating_cash_flow: Decimal | None
    investing_cash_flow: Decimal | None
    financing_cash_flow: Decimal | None
    net_cash_change: Decimal | None


@dataclass(frozen=True, slots=True)
class ValuationSummary:
    observed_at: datetime | None
    price_to_earnings_ttm: Decimal | None
    price_to_earnings_mrq: Decimal | None
    price_to_book_mrq: Decimal | None
    price_to_sales_ttm: Decimal | None
    price_to_cash_flow_ttm: Decimal | None


@dataclass(frozen=True, slots=True)
class TimeCatalyst:
    occurred_on: date
    title: str
    detail: str
    kind: str


@dataclass(frozen=True, slots=True)
class WatchlistFinancialDetail:
    """Published company data only; future events are never inferred."""

    instrument: Instrument
    observed_at: datetime
    source: str
    income_statement: IncomeStatementSummary | None
    balance_sheet: BalanceSheetSummary | None
    cash_flow: CashFlowSummary | None
    valuation: ValuationSummary | None
    time_catalysts: tuple[TimeCatalyst, ...]
    notices: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.source.strip():
            raise ValueError("source must not be empty")
