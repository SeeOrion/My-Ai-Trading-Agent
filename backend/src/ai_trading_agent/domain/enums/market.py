"""Market-wide stable enumerations."""

from enum import StrEnum


class Market(StrEnum):
    A_SHARE = "a_share"
    HONG_KONG = "hong_kong"
    UNITED_STATES = "united_states"
    FUND = "fund"


class InstrumentType(StrEnum):
    EQUITY = "equity"
    ETF = "etf"
    FUND = "fund"
    OPTION = "option"
