"""Pure rules for turning saved research into a closing-session review plan."""

from __future__ import annotations

from datetime import UTC, datetime, time
from zoneinfo import ZoneInfo

from ai_trading_agent.domain.aggregate.closing_plan import ClosingPlan, ClosingPlanItem
from ai_trading_agent.domain.aggregate.watchlist import WatchlistItem
from ai_trading_agent.domain.aggregate.watchlist_analysis import WatchlistAnalysisSnapshot
from ai_trading_agent.domain.enums.market import Market


def is_closing_window(market: Market, observed_at: datetime) -> bool:
    """Return whether an exchange-traded market is in its final 30 minutes."""
    timezone, start, end = {
        Market.A_SHARE: ("Asia/Shanghai", time(14, 30), time(15, 0)),
        Market.HONG_KONG: ("Asia/Hong_Kong", time(15, 30), time(16, 0)),
        Market.UNITED_STATES: ("America/New_York", time(15, 30), time(16, 0)),
    }.get(market, ("UTC", time(0, 0), time(0, 0)))
    instant = observed_at if observed_at.tzinfo is not None else observed_at.replace(tzinfo=UTC)
    local_now = instant.astimezone(ZoneInfo(timezone))
    return local_now.weekday() < 5 and start <= local_now.time().replace(tzinfo=None) < end


def closing_window_label(market: Market) -> str:
    return {
        Market.A_SHARE: "A 股尾盘窗口：14:30–15:00（北京时间）",
        Market.HONG_KONG: "港股尾盘窗口：15:30–16:00（香港时间）",
        Market.UNITED_STATES: "美股尾盘窗口：15:30–16:00（纽约时间）",
        Market.FUND: "场外基金按净值披露观察，不适用尾盘操作",
    }[market]


def build_closing_plan(
    items: list[WatchlistItem],
    analyses: list[WatchlistAnalysisSnapshot],
    *,
    generated_at: datetime,
) -> ClosingPlan:
    """Build a transparent next-session plan from persisted watchlist research."""
    analysis_by_item = {analysis.watchlist_item_id: analysis for analysis in analyses}
    plans = tuple(
        _item_plan(item, analysis_by_item.get(item.item_id), generated_at) for item in items
    )
    notices = [
        "尾盘计划仅供人工复核，不会发送真实订单；建议必须服从个人纪律与风险预算。",
        "计划基于最近一次已保存的自选研究快照；使用“刷新尾盘评估”可重新采集数据。",
    ]
    if any(item.instrument.market is Market.FUND for item in items):
        notices.append("场外基金按净值和披露数据观察，不生成盘中或尾盘买卖条件。")
    return ClosingPlan(generated_at=generated_at, items=plans, notices=tuple(notices))


def _item_plan(
    item: WatchlistItem,
    analysis: WatchlistAnalysisSnapshot | None,
    generated_at: datetime,
) -> ClosingPlanItem:
    in_window = is_closing_window(item.instrument.market, generated_at)
    label = item.label or item.instrument.symbol
    window = closing_window_label(item.instrument.market)
    if item.instrument.market is Market.FUND:
        return ClosingPlanItem(
            watchlist_item_id=item.item_id,
            instrument=item.instrument,
            label=label,
            action="observe",
            action_label="净值观察",
            closing_window=False,
            window_label=window,
            next_session_plan="等待下一次净值或披露更新，再结合长期纪律和资产配置复核。",
            reasons=("场外基金没有连续盘中成交价，不能套用尾盘操作逻辑。",),
            observed_at=None if analysis is None else analysis.observed_at,
            status="partial" if analysis is None else analysis.status.value,
        )
    if analysis is None or analysis.status.value == "failed":
        return ClosingPlanItem(
            watchlist_item_id=item.item_id,
            instrument=item.instrument,
            label=label,
            action="data_pending",
            action_label="等待数据",
            closing_window=in_window,
            window_label=window,
            next_session_plan="先刷新行情、因子与纪律状态；数据恢复前不形成建仓或加仓结论。",
            reasons=("尚无可用的自选研究快照。",),
            observed_at=None if analysis is None else analysis.observed_at,
            status="failed" if analysis is None else analysis.status.value,
        )

    action, action_label = _action_from_analysis(analysis)
    if action == "consider_entry" and not in_window:
        action, action_label = "observe", "等待尾盘确认"
    reasons = tuple(
        tag.label
        for tag in analysis.tags
        if tag.category in {"quote", "factors", "trend", "momentum", "volume", "sentiment", "capital_flow", "discipline"}
    )[:4]
    return ClosingPlanItem(
        watchlist_item_id=item.item_id,
        instrument=item.instrument,
        label=label,
        action=action,
        action_label=action_label,
        closing_window=in_window,
        window_label=window,
        next_session_plan=_next_session_plan(action, in_window),
        reasons=reasons or ("已保存研究快照未包含足够的可展示标签。",),
        observed_at=analysis.observed_at,
        status=analysis.status.value,
    )


def _action_from_analysis(analysis: WatchlistAnalysisSnapshot) -> tuple[str, str]:
    action_tag = next((tag.label for tag in analysis.tags if tag.category == "action"), "")
    mapping = (
        ("清仓复核", "exit_review", "清仓复核"),
        ("止盈复核", "take_profit_review", "止盈复核"),
        ("加仓条件满足", "consider_add", "加仓条件满足"),
        ("可考虑建仓", "consider_entry", "可考虑买入"),
    )
    for phrase, action, label in mapping:
        if phrase in action_tag:
            return action, label
    return "observe", "观察"


def _next_session_plan(action: str, in_window: bool) -> str:
    if action == "exit_review":
        return "下一交易日优先复核个人纪律的清仓价位；未满足前不自动卖出。"
    if action == "take_profit_review":
        return "下一交易日按个人纪律复核止盈价位与趋势，避免把止盈信号视为自动卖出。"
    if action == "consider_add":
        return "仅在下一交易日价格、纪律和剩余风险预算同时满足时，再人工复核加仓。"
    if action == "consider_entry":
        return "尾盘条件初步满足；记录候选价位，下一交易日开盘后确认流动性与纪律再决定。"
    if action == "data_pending":
        return "数据恢复前保持观察，不据此建立或调整模拟仓位。"
    return (
        "当前不在尾盘确认窗口，等待尾盘数据后再复核。"
        if not in_window
        else "尾盘信号不足，保留观察并等待下一交易日确认。"
    )
