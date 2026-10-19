"""Choose a monthly mark without counting pre-purchase price changes as profit."""

from zoneinfo import ZoneInfo


def monthly_basis(position, quote, reference):
    zone = ZoneInfo(
        {
            "a_share": "Asia/Shanghai",
            "fund": "Asia/Shanghai",
            "hong_kong": "Asia/Hong_Kong",
            "united_states": "America/New_York",
        }[position.instrument.market.value]
    )
    as_of = quote.observed_at.astimezone(zone).date()
    opened = position.opened_at.astimezone(zone).date() if position.opened_at else None
    if opened and opened > as_of:
        return None, None, "收盘日期早于买入日期，无法计算该持仓月盈亏。"
    if opened and opened.replace(day=1) == as_of.replace(day=1):
        return position.average_cost, opened, "本月买入：以买入均价计算当前持仓月盈亏。"
    if reference is not None:
        return reference[1], reference[0], "以月初前收盘价计算当前持仓月盈亏。"
    return (
        position.average_cost,
        None,
        "月初基准缺失：按买入成本估算，属于持仓累计盈亏，不是严格月收益。",
    )
