from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from ai_trading_agent.domain.enums.candidates import CandidateRanking
from ai_trading_agent.domain.enums.market import Market
from ai_trading_agent.interfaces.facade import research_workspace as workspace


@pytest.mark.asyncio
async def test_cached_screen_keeps_timestamp_first_and_separates_limits(monkeypatch):
    monkeypatch.setattr(workspace, "_candidate_screen_cache", {})
    screen = SimpleNamespace(candidates=(), universe_size=10)
    handler = SimpleNamespace(handle=AsyncMock(return_value=screen))
    monkeypatch.setattr(workspace, "_candidate_provider", lambda market: object())
    monkeypatch.setattr(workspace, "RankMarketCandidatesHandler", lambda provider: handler)
    monkeypatch.setattr(workspace, "_enrich_candidate_names", AsyncMock(return_value=screen))
    first = await workspace.today_candidates(Market.A_SHARE, CandidateRanking.BALANCED_ENTRY, limit=10)
    cached = await workspace.today_candidates(Market.A_SHARE, CandidateRanking.BALANCED_ENTRY, limit=10)
    assert cached == first
    handler.handle.assert_awaited_once()
    await workspace.today_candidates(Market.A_SHARE, CandidateRanking.BALANCED_ENTRY, limit=3)
    assert handler.handle.await_count == 2
