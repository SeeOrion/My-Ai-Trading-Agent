from copy import deepcopy

import pytest

from ai_trading_agent.domain.service.summary_reuse import (
    important_news_titles,
    summary_change_reason,
)


def baseline():
    return {
        "version": 1,
        "action": ["observe"],
        "disciplines": {},
        "strategies": [],
        "signals": {"trend": "neutral"},
        "news": ["公司发布业绩预告"],
        "factors": {"momentum": {"value": "10", "direction": "neutral"}},
    }


def test_ignore_timestamps_noise_and_small_changes_but_accumulate_from_generation():
    old = baseline()
    current = deepcopy(old)
    current.update(observed_at="tomorrow", source="another-provider", request_id="random")
    current["factors"]["momentum"]["value"] = "10.9"
    assert summary_change_reason(old, current) is None
    current["factors"]["momentum"]["value"] = "11"
    assert summary_change_reason(old, current) == "关键因子明显变化"


@pytest.mark.parametrize(
    "field,value",
    [
        ("action", ["exit"]),
        ("disciplines", {"one": "take_profit"}),
        ("strategies", ["new"]),
        ("signals", {"trend": "bearish"}),
        ("news", ["公司宣布重大重组"]),
        ("factors", {"momentum": {"value": "10", "direction": "bearish"}}),
        ("factors", {"momentum": {"value": None, "direction": "unavailable"}}),
    ],
)
def test_semantic_triggers(field, value):
    old = baseline()
    new = deepcopy(old)
    new[field] = value
    assert summary_change_reason(old, new)


def test_news_rolloff_does_not_trigger_and_titles_are_deduplicated():
    old, new = baseline(), baseline()
    new["news"] = []
    assert summary_change_reason(old, new) is None
    assert important_news_titles(["公司 业绩 预告", "公司业绩预告", "今日市场观察"]) == [
        "公司业绩预告"
    ]
