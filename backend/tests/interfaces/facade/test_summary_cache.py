from datetime import UTC, datetime
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from fastapi import FastAPI

from ai_trading_agent.domain.aggregate.market import Instrument, Quote
from ai_trading_agent.domain.aggregate.watchlist import WatchlistItem
from ai_trading_agent.domain.enums.market import Market
from ai_trading_agent.infrastructure.config.providers import (
    AiSimulationSchedulerSettings,
    WatchlistAnalysisSettings,
)
from ai_trading_agent.interfaces.facade import watchlist_analysis as service
from ai_trading_agent.interfaces.model.http import ResearchResponse


@pytest.mark.asyncio
async def test_persisted_summary_reused_after_restart_but_manual_refresh_regenerates(monkeypatch):
    saved = None

    async def get(_):
        return saved

    async def save(value):
        nonlocal saved
        saved = value
        return value

    repo = SimpleNamespace(get_latest=get, save=save)
    item = WatchlistItem(uuid4(), Instrument("600519.SH", Market.A_SHARE))
    monkeypatch.setattr(service, "watchlist_analysis_repository", lambda app: repo)
    monkeypatch.setattr(
        service,
        "latest_quote",
        AsyncMock(return_value=Quote(item.instrument, Decimal(100), datetime.now(UTC), "test")),
    )
    monkeypatch.setattr(
        service,
        "research",
        AsyncMock(
            return_value=ResearchResponse(
                symbol=item.instrument.symbol,
                market=Market.A_SHARE,
                fundamentals=None,
                capital_flow=None,
                news_sentiment=None,
                notices=[],
            )
        ),
    )
    monkeypatch.setattr(
        service, "strategy_repository", lambda app: SimpleNamespace(list=AsyncMock(return_value=[]))
    )
    monkeypatch.setattr(
        service,
        "technical_study",
        AsyncMock(
            return_value=SimpleNamespace(
                assessment={
                    "trend": "neutral",
                    "momentum": "neutral",
                    "volume_pressure": "neutral",
                },
                indicators={},
            )
        ),
    )
    monkeypatch.setattr(service, "evaluate_active_disciplines", AsyncMock(return_value=[]))
    monkeypatch.setattr(service, "record_usage", AsyncMock())
    summarize = AsyncMock(return_value="行动：观察。依据：信号未改变。")
    monkeypatch.setattr(service, "_summarize_with_ai", summarize)
    first = await service.refresh_watchlist_analysis(FastAPI(), item, force=True)
    second = await service.refresh_watchlist_analysis(FastAPI(), item, force=True)
    assert summarize.await_count == 1
    assert second.summary_generated_at == first.summary_generated_at
    assert any("复用" in t.label for t in second.tags)
    await service.refresh_watchlist_analysis(FastAPI(), item, force=True, force_summary=True)
    assert summarize.await_count == 2


def test_summary_cadence_is_separate_from_simulated_trading(monkeypatch):
    monkeypatch.delenv("WATCHLIST_RESEARCH_INTERVAL_SECONDS", raising=False)
    monkeypatch.delenv("AI_SIMULATION_INTERVAL_SECONDS", raising=False)
    monkeypatch.setenv("WATCHLIST_ANALYSIS_INTERVAL_SECONDS", "900")
    assert WatchlistAnalysisSettings.from_environment().interval_seconds == 3600
    assert AiSimulationSchedulerSettings.from_environment().interval_seconds == 600
