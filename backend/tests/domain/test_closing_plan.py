from datetime import UTC, datetime
from uuid import uuid4

from ai_trading_agent.domain.aggregate.market import Instrument
from ai_trading_agent.domain.aggregate.watchlist import WatchlistItem
from ai_trading_agent.domain.aggregate.watchlist_analysis import AnalysisTag, WatchlistAnalysisSnapshot
from ai_trading_agent.domain.enums.market import Market
from ai_trading_agent.domain.enums.research import WatchlistAnalysisStatus
from ai_trading_agent.domain.service.closing_plan import build_closing_plan, is_closing_window


def test_a_share_closing_window_uses_beijing_time() -> None:
    assert is_closing_window(Market.A_SHARE, datetime(2026, 9, 23, 6, 45, tzinfo=UTC))
    assert not is_closing_window(Market.A_SHARE, datetime(2026, 9, 23, 7, 0, tzinfo=UTC))


def test_closing_plan_retains_entry_candidate_only_inside_closing_window() -> None:
    item = WatchlistItem(uuid4(), Instrument("600519.SH", Market.A_SHARE), "贵州茅台")
    analysis = WatchlistAnalysisSnapshot(
        analysis_id=uuid4(),
        watchlist_item_id=item.item_id,
        instrument=item.instrument,
        observed_at=datetime(2026, 9, 23, 6, 40, tzinfo=UTC),
        status=WatchlistAnalysisStatus.COMPLETED,
        tags=(
            AnalysisTag("action", "动作：可考虑建仓 · 价位 1400"),
            AnalysisTag("factors", "因子：8/10 可用 · 支持 6 · 风险 1", "positive"),
        ),
        ai_summary=None,
    )

    plan = build_closing_plan(
        [item], [analysis], generated_at=datetime(2026, 9, 23, 6, 45, tzinfo=UTC)
    )

    assert plan.items[0].action == "consider_entry"
    assert plan.items[0].action_label == "可考虑买入"


def test_closing_plan_waits_for_data_when_no_snapshot_exists() -> None:
    item = WatchlistItem(uuid4(), Instrument("0700.HK", Market.HONG_KONG), "腾讯控股")

    plan = build_closing_plan(
        [item], [], generated_at=datetime(2026, 9, 23, 7, 45, tzinfo=UTC)
    )

    assert plan.items[0].action == "data_pending"
    assert "不形成建仓" in plan.items[0].next_session_plan
