"""Deterministic summary invalidation; no clocks, providers or LLM dependencies."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation


def summary_change_reason(previous: dict | None, current: dict) -> str | None:
    """Compare against the last generated summary, never the last polling sample.

    Factor direction/availability changes always matter. Numeric changes require
    both a 10% relative change and a 0.01 absolute change (in the factor's units).
    Only explicitly selected semantic fields enter this state, not raw responses.
    """
    if not previous or previous.get("version") != current.get("version"):
        return "首次生成"
    for key, label in (
        ("action", "行动状态变化"),
        ("disciplines", "纪律触发或配置变化"),
        ("strategies", "策略变化"),
        ("signals", "研究信号变化"),
    ):
        if previous.get(key) != current.get(key):
            return label
    if set(current.get("news", [])) - set(previous.get("news", [])):
        return "重要新闻出现"
    before, after = previous.get("factors", {}), current.get("factors", {})
    if before.keys() != after.keys():
        return "因子可用性变化"
    for key, value in after.items():
        old = before[key]
        if old.get("direction") != value.get("direction"):
            return "因子方向变化"
        a, b = old.get("value"), value.get("value")
        if (a is None) != (b is None):
            return "因子可用性变化"
        try:
            x, y = Decimal(str(a)), Decimal(str(b))
            if (
                x.is_finite()
                and y.is_finite()
                and abs(y - x) >= max(abs(x) * Decimal("0.1"), Decimal("0.01"))
            ):
                return "关键因子明显变化"
        except InvalidOperation:
            if a != b:
                return "因子变化"
    return None


IMPORTANT_NEWS_TERMS = (
    "业绩",
    "财报",
    "分红",
    "并购",
    "重组",
    "回购",
    "减持",
    "增持",
    "违约",
    "处罚",
    "立案",
    "退市",
    "停牌",
    "复牌",
    "降息",
    "加息",
    "关税",
    "盈利预警",
)


def important_news_titles(titles: list[str]) -> list[str]:
    """Transparent heuristic, not a claim to identify every material event."""
    return sorted(
        {
            "".join(title.split())
            for title in titles
            if any(term in title for term in IMPORTANT_NEWS_TERMS)
        }
    )[:30]
