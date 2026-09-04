"""Stable classifications emitted by research services."""

from enum import StrEnum


class FlowDirection(StrEnum):
    INFLOW = "inflow"
    OUTFLOW = "outflow"
    NEUTRAL = "neutral"


class SentimentLabel(StrEnum):
    POSITIVE = "positive"
    NEUTRAL = "neutral"
    NEGATIVE = "negative"


class OptionKind(StrEnum):
    CALL = "call"
    PUT = "put"


class PositionSide(StrEnum):
    LONG = "long"
    SHORT = "short"


class DisciplineStatus(StrEnum):
    ACTIVE = "active"
    PAUSED = "paused"
    ARCHIVED = "archived"
