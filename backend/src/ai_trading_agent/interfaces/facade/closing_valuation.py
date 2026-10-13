"""Read-only closing valuation; never executes simulation decisions."""

import asyncio
from datetime import datetime

from ai_trading_agent.domain.aggregate.market import Instrument, Quote
from ai_trading_agent.infrastructure.market_data.exchange_calendar import ExchangeTradingCalendar
from ai_trading_agent.interfaces.facade.research_workspace import historical_bars_provider


async def closing_quote_and_bars(instrument: Instrument, now: datetime):
    provider = historical_bars_provider(instrument, unadjusted=True)
    for attempt in range(2):
        try:
            bars = await asyncio.wait_for(provider.get_daily_bars(instrument, limit=90), timeout=30)
            break
        except Exception as error:
            transient = isinstance(error, TimeoutError) or any(
                marker in str(error).lower()
                for marker in ("timed out", "name or service not known", "connection reset")
            )
            if not transient or attempt == 1:
                raise
            await asyncio.sleep(0.5)
    calendar = ExchangeTradingCalendar()
    completed = [
        (bar, calendar.completed_close(instrument.market, bar.session_date, now)) for bar in bars
    ]
    completed = sorted(
        ((bar, close) for bar, close in completed if close is not None),
        key=lambda item: item[0].session_date,
    )
    if not completed:
        raise ValueError("没有已结束交易日的收盘价")
    latest, close = completed[-1]
    quote = Quote(
        instrument,
        latest.close_price,
        close,
        f"{provider.name}:close_unadjusted",
        previous_close=completed[-2][0].close_price if len(completed) > 1 else None,
    )
    return (
        quote,
        tuple(bar for bar, _ in completed),
        (
            f"{instrument.symbol} 按 {latest.session_date} 未复权收盘价估值；"
            "涨跌与月盈亏截至该交易日，若今日未收盘或尚未披露日线，将使用之前可用收盘价。"
        ),
    )
