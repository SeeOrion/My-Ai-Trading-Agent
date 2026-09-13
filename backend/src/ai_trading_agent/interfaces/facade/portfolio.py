"""Composition helpers for private watchlist and paper-position features."""

from __future__ import annotations

import asyncio
from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import UUID

from fastapi import FastAPI

from ai_trading_agent.domain.aggregate.market import Instrument
from ai_trading_agent.domain.aggregate.technical import PriceBar
from ai_trading_agent.domain.aggregate.watchlist import (
    PaperPortfolioOverview,
    PaperPosition,
    PaperPositionValuation,
    WatchlistItem,
    summarize_paper_portfolio,
    value_paper_position,
)
from ai_trading_agent.infrastructure.repo.portfolio import (
    SqlAlchemyPaperPositionRepository,
    SqlAlchemyWatchlistAnalysisRepository,
    SqlAlchemyWatchlistRepository,
)
from ai_trading_agent.interfaces.facade.persistence import private_session_factory
from ai_trading_agent.interfaces.facade.research_workspace import (
    historical_daily_bars,
    latest_quote,
)
from ai_trading_agent.interfaces.model.http import PaperPositionInput, WatchlistInput


def watchlist_repository(app: FastAPI) -> SqlAlchemyWatchlistRepository:
    return SqlAlchemyWatchlistRepository(private_session_factory(app))


def paper_position_repository(app: FastAPI) -> SqlAlchemyPaperPositionRepository:
    return SqlAlchemyPaperPositionRepository(private_session_factory(app))


def watchlist_analysis_repository(app: FastAPI) -> SqlAlchemyWatchlistAnalysisRepository:
    return SqlAlchemyWatchlistAnalysisRepository(private_session_factory(app))


async def get_watchlist_item(app: FastAPI, item_id: UUID) -> WatchlistItem | None:
    return await watchlist_repository(app).get(str(item_id))


def watchlist_from_input(payload: WatchlistInput, item_id: UUID) -> WatchlistItem:
    return WatchlistItem(
        item_id,
        Instrument(payload.symbol, payload.market, payload.instrument_type),
        payload.label,
        payload.notes,
    )


def paper_position_from_input(payload: PaperPositionInput, position_id: UUID) -> PaperPosition:
    return PaperPosition(
        position_id,
        Instrument(payload.symbol, payload.market, payload.instrument_type),
        payload.quantity,
        payload.average_cost,
        payload.notes,
    )


async def paper_portfolio_overview(
    positions: list[PaperPosition], *, now: datetime | None = None
) -> PaperPortfolioOverview:
    """Refresh a small manual portfolio with per-currency performance metrics."""
    observed_at = (now or datetime.now(UTC)).astimezone(UTC)
    month_start = observed_at.date().replace(day=1)
    semaphore = asyncio.Semaphore(4)
    results = await asyncio.gather(
        *(
            _value_position_with_references(position, month_start, semaphore)
            for position in positions
        )
    )
    valuations: list[PaperPositionValuation] = []
    notices: list[str] = []
    for valuation, position_notices in results:
        if valuation is not None:
            valuations.append(valuation)
        notices.extend(position_notices)
    summary = summarize_paper_portfolio(
        tuple(valuations), observed_at=observed_at, total_position_count=len(positions)
    )
    if len(valuations) < len(positions):
        notices.append("部分持仓行情不可用，组合总计仅覆盖已成功估值的持仓。")
    return PaperPortfolioOverview(
        valuations=tuple(valuations),
        summary=summary,
        notices=tuple(dict.fromkeys(notices)),
    )


async def _value_position_with_references(
    position: PaperPosition,
    month_start: date,
    semaphore: asyncio.Semaphore,
) -> tuple[PaperPositionValuation | None, tuple[str, ...]]:
    """Use a quote for daily change and one prior-month close for the MTD estimate."""
    async with semaphore:
        quote_result, bars_result = await asyncio.gather(
            latest_quote(position.instrument),
            historical_daily_bars(position.instrument, limit=90),
            return_exceptions=True,
        )
    if isinstance(quote_result, Exception):
        return None, (f"{position.instrument.symbol} 行情不可用，未纳入组合估值。",)

    notices: list[str] = []
    reference_close = None
    reference_date = None
    if isinstance(bars_result, Exception):
        notices.append(f"{position.instrument.symbol} 月初收盘价不可用，未计算月盈亏。")
    else:
        reference = _month_reference_close(bars_result, month_start)
        if reference is None:
            notices.append(f"{position.instrument.symbol} 缺少月初前收盘价，未计算月盈亏。")
        else:
            reference_date, reference_close = reference
    return (
        value_paper_position(
            position,
            quote_result,
            month_reference_close=reference_close,
            month_reference_date=reference_date,
        ),
        tuple(notices),
    )


def _month_reference_close(
    bars: tuple[PriceBar, ...], month_start: date
) -> tuple[date, Decimal] | None:
    """Select the final available close before this calendar month begins."""
    previous = [bar for bar in bars if bar.session_date < month_start]
    if not previous:
        return None
    selected = max(previous, key=lambda bar: bar.session_date)
    return selected.session_date, selected.close_price
