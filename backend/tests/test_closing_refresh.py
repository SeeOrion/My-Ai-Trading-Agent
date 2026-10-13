from datetime import UTC, date, datetime
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from ai_trading_agent.domain.aggregate.market import Instrument
from ai_trading_agent.domain.aggregate.technical import PriceBar
from ai_trading_agent.domain.enums.market import Market
from ai_trading_agent.domain.service.simulation_failure import simulation_failure_message
from ai_trading_agent.infrastructure.market_data.exchange_calendar import ExchangeTradingCalendar
from ai_trading_agent.interfaces.facade import closing_valuation
from ai_trading_agent.interfaces.task.market_scans import RecurringTaskScheduler


@pytest.mark.asyncio
async def test_closing_refresh_excludes_incomplete_session(monkeypatch):
    instrument = Instrument("600519.SH", Market.A_SHARE)

    def bar(day, price):
        p = Decimal(price)
        return PriceBar(instrument, date(2026, 10, day), p, p, p, p, Decimal(100))

    provider = SimpleNamespace(
        name="test", get_daily_bars=AsyncMock(return_value=(bar(12, "100"), bar(13, "105")))
    )

    def factory(value, *, unadjusted=False):
        assert value == instrument and unadjusted
        return provider

    monkeypatch.setattr(closing_valuation, "historical_bars_provider", factory)
    quote, bars, notice = await closing_valuation.closing_quote_and_bars(
        instrument, datetime(2026, 10, 13, 6, tzinfo=UTC)
    )
    assert quote.last_price == Decimal(100)
    assert len(bars) == 1 and "2026-10-12" in notice
    quote, bars, _ = await closing_valuation.closing_quote_and_bars(
        instrument, datetime(2026, 10, 13, 7, tzinfo=UTC)
    )
    assert quote.last_price == Decimal(105) and quote.previous_close == Decimal(100)


def test_holiday_is_not_a_completed_session():
    assert (
        ExchangeTradingCalendar().completed_close(
            Market.A_SHARE, date(2026, 10, 1), datetime(2026, 10, 13, tzinfo=UTC)
        )
        is None
    )


@pytest.mark.parametrize(
    "delay,confirmed,prefix",
    [(0, False, "Name"), (90, False, "疑似电脑休眠中"), (0, True, "电脑休眠中")],
)
def test_sleep_failure_requires_evidence(delay, confirmed, prefix):
    message, notes = simulation_failure_message(
        "Name or service not known", Market.A_SHARE, resume_delay=delay, confirmed_sleep=confirmed
    )
    assert message.startswith(prefix)
    assert bool(notes) == (confirmed or delay >= 60)


def test_permission_failure_not_mislabeled_as_sleep():
    assert simulation_failure_message("无权限订阅", Market.A_SHARE, resume_delay=90) == (
        "无权限订阅",
        (),
    )


@pytest.mark.asyncio
async def test_scheduler_measures_resume_delay(monkeypatch):
    scheduler = RecurringTaskScheduler(AsyncMock(), 600)
    ticks = iter([1000, 1700])
    monkeypatch.setattr(
        "ai_trading_agent.interfaces.task.market_scans.time.time", lambda: next(ticks)
    )
    scheduler._stop_requested.set()
    await scheduler._wait(600)
    assert scheduler.resume_delay_seconds == 100


@pytest.mark.asyncio
async def test_closing_timeout_retries_once(monkeypatch):
    instrument = Instrument("600519.SH", Market.A_SHARE)
    p = Decimal(100)
    bar = PriceBar(instrument, date(2026, 10, 12), p, p, p, p, p)
    fetch = AsyncMock(side_effect=[TimeoutError(), (bar,)])
    monkeypatch.setattr(closing_valuation, "historical_bars_provider",
                        lambda *a, **kw: SimpleNamespace(name="test", get_daily_bars=fetch))
    quote, _, _ = await closing_valuation.closing_quote_and_bars(
        instrument, datetime(2026, 10, 13, tzinfo=UTC))
    assert fetch.await_count == 2 and quote.last_price == p
