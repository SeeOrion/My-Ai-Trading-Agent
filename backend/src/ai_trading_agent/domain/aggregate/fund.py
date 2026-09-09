"""Fund research concepts independent of any upstream financial-data vendor."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal

from ai_trading_agent.domain.aggregate.market import Instrument


@dataclass(frozen=True, slots=True)
class FundOverview:
    name: str | None
    management_company: str | None
    manager_name: str | None
    fund_scale: Decimal | None
    latest_unit_nav: Decimal | None


@dataclass(frozen=True, slots=True)
class FundNavPoint:
    nav_date: date
    unit_nav: Decimal | None
    adjusted_nav: Decimal | None


@dataclass(frozen=True, slots=True)
class FundHolding:
    name: str
    asset_type: str | None
    weight_percent: Decimal | None
    market_value: Decimal | None
    disclosed_at: date | None


@dataclass(frozen=True, slots=True)
class FundAllocation:
    report_date: date | None
    stock_percent: Decimal | None
    bond_percent: Decimal | None
    cash_percent: Decimal | None
    other_percent: Decimal | None


@dataclass(frozen=True, slots=True)
class FundNews:
    title: str
    summary: str | None
    publisher: str | None
    url: str | None
    published_at: datetime | None


@dataclass(frozen=True, slots=True)
class FundResearchReport:
    """One selected fund's disclosed and market data with its source boundaries."""

    instrument: Instrument
    observed_at: datetime
    source: str
    overview: FundOverview
    nav_history: tuple[FundNavPoint, ...]
    returns_percent: dict[str, Decimal | None]
    drawdowns_percent: dict[str, Decimal | None]
    holdings: tuple[FundHolding, ...]
    allocations: tuple[FundAllocation, ...]
    institutional_holding_percent: Decimal | None
    latest_financials: dict[str, Decimal | None]
    diagnostics: dict[str, object]
    news: tuple[FundNews, ...]
    limitations: tuple[str, ...]
