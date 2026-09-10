from datetime import datetime
from uuid import uuid4

import pytest

from ai_trading_agent.domain.aggregate.market import Instrument
from ai_trading_agent.domain.aggregate.watchlist_analysis import (
    AnalysisTag,
    WatchlistAnalysisSnapshot,
)
from ai_trading_agent.domain.enums.market import Market
from ai_trading_agent.domain.enums.research import WatchlistAnalysisStatus


def test_watchlist_analysis_snapshot_requires_a_timezone_aware_observation() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        WatchlistAnalysisSnapshot(
            analysis_id=uuid4(),
            watchlist_item_id=uuid4(),
            instrument=Instrument("600519.SH", Market.A_SHARE),
            observed_at=datetime.now(),
            status=WatchlistAnalysisStatus.COMPLETED,
            tags=(AnalysisTag("sentiment", "情绪：积极", "positive"),),
            ai_summary="数据摘要",
        )


def test_watchlist_analysis_tag_rejects_unknown_tone() -> None:
    with pytest.raises(ValueError, match="unsupported"):
        AnalysisTag("sentiment", "情绪：积极", "unknown")
