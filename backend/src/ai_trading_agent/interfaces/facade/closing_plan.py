"""Composition for the review-only closing-session workspace."""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import FastAPI

from ai_trading_agent.application.closing_plan import BuildClosingPlanHandler
from ai_trading_agent.application.portfolio import ListWatchlistHandler
from ai_trading_agent.domain.aggregate.closing_plan import ClosingPlan
from ai_trading_agent.domain.service.closing_plan import is_closing_window
from ai_trading_agent.infrastructure.config.providers import WatchlistAnalysisSettings
from ai_trading_agent.interfaces.facade.portfolio import watchlist_repository
from ai_trading_agent.interfaces.facade.watchlist_analysis import (
    latest_watchlist_analyses,
    refresh_watchlist_analysis,
)


async def closing_plan(app: FastAPI, *, generated_at: datetime | None = None) -> ClosingPlan:
    """Return the latest saved plan without issuing network requests on GET."""
    items = await ListWatchlistHandler(watchlist_repository(app)).handle()
    analyses = await latest_watchlist_analyses(app)
    return BuildClosingPlanHandler().handle(
        items,
        analyses,
        generated_at=generated_at or datetime.now(UTC),
    )


async def refresh_closing_plan(app: FastAPI) -> ClosingPlan:
    """Explicit user refresh for all bounded, personally selected instruments."""
    settings = WatchlistAnalysisSettings.from_environment()
    items = (await ListWatchlistHandler(watchlist_repository(app)).handle())[
        : settings.max_items_per_run
    ]
    for item in items:
        await refresh_watchlist_analysis(app, item, force=True)
    return await closing_plan(app)


async def refresh_closing_window_analyses(
    app: FastAPI, *, observed_at: datetime | None = None
) -> None:
    """Refresh only selected exchange-traded items during each market's final 30 minutes."""
    now = observed_at or datetime.now(UTC)
    settings = WatchlistAnalysisSettings.from_environment()
    items = (await ListWatchlistHandler(watchlist_repository(app)).handle())[
        : settings.max_items_per_run
    ]
    for item in items:
        if not is_closing_window(item.instrument.market, now):
            continue
        try:
            await refresh_watchlist_analysis(app, item, force=True)
        except Exception:
            # A single unavailable public source must not block the other selected items.
            continue
