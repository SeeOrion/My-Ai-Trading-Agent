"""Vocabulary shared by technical-analysis use cases."""

from __future__ import annotations

from enum import StrEnum


class BarTimeframe(StrEnum):
    """Research aggregation period, never a provider-specific kline name."""

    DAILY = "1d"
    WEEKLY = "1w"
    MONTHLY = "1m"


class TechnicalBias(StrEnum):
    BULLISH = "bullish"
    BEARISH = "bearish"
    NEUTRAL = "neutral"
