"""Application use case for building a personal closing-session review plan."""

from __future__ import annotations

from datetime import datetime

from ai_trading_agent.domain.aggregate.closing_plan import ClosingPlan
from ai_trading_agent.domain.aggregate.watchlist import WatchlistItem
from ai_trading_agent.domain.aggregate.watchlist_analysis import WatchlistAnalysisSnapshot
from ai_trading_agent.domain.service.closing_plan import build_closing_plan


class BuildClosingPlanHandler:
    def handle(
        self,
        items: list[WatchlistItem],
        analyses: list[WatchlistAnalysisSnapshot],
        *,
        generated_at: datetime,
    ) -> ClosingPlan:
        return build_closing_plan(items, analyses, generated_at=generated_at)
