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


class DisciplineDecisionStatus(StrEnum):
    """Deterministic review states produced from an active price discipline.

    These values intentionally describe a condition for manual review.  They
    are not brokerage order types and must never be interpreted as an
    instruction to submit an order.
    """

    OBSERVE = "observe"
    BUY_CANDIDATE = "buy_candidate"
    ADD_CONDITION_MET = "add_condition_met"
    TAKE_PROFIT = "take_profit"
    EXIT = "exit"


class WatchlistAnalysisStatus(StrEnum):
    COMPLETED = "completed"
    PARTIAL = "partial"
    FAILED = "failed"
