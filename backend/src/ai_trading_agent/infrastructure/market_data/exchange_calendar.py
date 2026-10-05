"""Offline exchange-calendar adapter for scheduled simulation jobs."""

from __future__ import annotations

from datetime import UTC, datetime
from functools import lru_cache
from zoneinfo import ZoneInfo

import exchange_calendars as exchange_calendars
from exchange_calendars.errors import DateOutOfBounds, MinuteOutOfBounds
from exchange_calendars.exchange_calendar import ExchangeCalendar
from pandas import Timestamp

from ai_trading_agent.domain.enums.market import Market

_CALENDAR_NAMES = {
    Market.A_SHARE: "XSHG",
    Market.FUND: "XSHG",
    Market.HONG_KONG: "XHKG",
    Market.UNITED_STATES: "XNYS",
}


class ExchangeTradingCalendar:
    """Use maintained exchange schedules and fail closed outside their known range."""

    def is_trading_day(self, market: Market, observed_at: datetime) -> bool:
        calendar = _calendar(market)
        instant = _aware_utc(observed_at)
        local_date = instant.astimezone(calendar.tz).date()
        try:
            return bool(calendar.is_session(Timestamp(local_date)))
        except DateOutOfBounds:
            return False

    def is_open(self, market: Market, observed_at: datetime) -> bool:
        calendar = _calendar(market)
        instant = _aware_utc(observed_at)
        utc_minute = instant.astimezone(UTC).replace(second=0, microsecond=0, tzinfo=None)
        minute = Timestamp(utc_minute, tz=ZoneInfo("UTC"))
        try:
            return bool(calendar.is_open_on_minute(minute, ignore_breaks=False))
        except MinuteOutOfBounds:
            return False


@lru_cache(maxsize=len(_CALENDAR_NAMES))
def _calendar(market: Market) -> ExchangeCalendar:
    try:
        name = _CALENDAR_NAMES[market]
    except KeyError as error:
        raise ValueError(f"unsupported trading calendar market: {market}") from error
    # "left" makes the open minute inclusive and the close minute exclusive.
    return exchange_calendars.get_calendar(name, side="left")


def _aware_utc(observed_at: datetime) -> datetime:
    if observed_at.tzinfo is None:
        return observed_at.replace(tzinfo=UTC)
    return observed_at.astimezone(UTC)
