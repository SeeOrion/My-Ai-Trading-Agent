from datetime import UTC, datetime

from ai_trading_agent.domain.enums.market import Market
from ai_trading_agent.infrastructure.market_data.exchange_calendar import (
    ExchangeTradingCalendar,
)


def test_a_share_national_day_is_not_a_trading_day() -> None:
    calendar = ExchangeTradingCalendar()
    national_day_break = datetime(2026, 10, 5, 1, 30, tzinfo=UTC)

    assert not calendar.is_trading_day(Market.A_SHARE, national_day_break)
    assert not calendar.is_open(Market.A_SHARE, national_day_break)


def test_markets_use_independent_exchange_holidays() -> None:
    calendar = ExchangeTradingCalendar()
    hong_kong_open = datetime(2026, 10, 5, 1, 30, tzinfo=UTC)
    new_york_open = datetime(2026, 10, 5, 13, 30, tzinfo=UTC)

    assert calendar.is_trading_day(Market.HONG_KONG, hong_kong_open)
    assert calendar.is_open(Market.HONG_KONG, hong_kong_open)
    assert calendar.is_trading_day(Market.UNITED_STATES, new_york_open)
    assert calendar.is_open(Market.UNITED_STATES, new_york_open)


def test_a_share_lunch_break_and_close_are_not_open() -> None:
    calendar = ExchangeTradingCalendar()

    assert calendar.is_open(Market.A_SHARE, datetime(2026, 9, 18, 1, 30, tzinfo=UTC))
    assert not calendar.is_open(
        Market.A_SHARE, datetime(2026, 9, 18, 3, 30, tzinfo=UTC)
    )
    assert calendar.is_open(Market.A_SHARE, datetime(2026, 9, 18, 5, 0, tzinfo=UTC))
    assert not calendar.is_open(Market.A_SHARE, datetime(2026, 9, 18, 7, 0, tzinfo=UTC))


def test_us_session_follows_daylight_saving_time() -> None:
    calendar = ExchangeTradingCalendar()

    assert calendar.is_open(
        Market.UNITED_STATES, datetime(2026, 9, 18, 13, 30, tzinfo=UTC)
    )
    assert not calendar.is_open(
        Market.UNITED_STATES, datetime(2026, 11, 2, 13, 30, tzinfo=UTC)
    )
    assert calendar.is_open(
        Market.UNITED_STATES, datetime(2026, 11, 2, 14, 30, tzinfo=UTC)
    )


def test_calendar_fails_closed_outside_known_schedule_range() -> None:
    calendar = ExchangeTradingCalendar()
    unknown_future = datetime(2099, 1, 5, 1, 30, tzinfo=UTC)

    assert not calendar.is_trading_day(Market.A_SHARE, unknown_future)
    assert not calendar.is_open(Market.A_SHARE, unknown_future)
