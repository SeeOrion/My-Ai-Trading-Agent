"""Read-only closing valuation; never executes simulation decisions."""

import asyncio
from datetime import datetime

from ai_trading_agent.domain.ability.closing_prices import ClosingPriceRepository, ClosingPrices
from ai_trading_agent.domain.aggregate.market import Instrument, Quote
from ai_trading_agent.infrastructure.market_data.exchange_calendar import ExchangeTradingCalendar
from ai_trading_agent.interfaces.facade.research_workspace import historical_bars_provider


async def closing_quote_and_bars(
    instrument: Instrument, now: datetime, cache: ClosingPriceRepository | None = None
):
    note = ""
    try:
        quote, bars, note = await _fetch_closing_quote_and_bars(instrument, now)
    except Exception:
        snapshot = await cache.get(instrument) if cache is not None else None
        target = ExchangeTradingCalendar().latest_completed_session(instrument.market, now)
        if snapshot is None or not snapshot.bars or snapshot.bars[-1].session_date != target:
            raise
        bars = snapshot.bars
        quote = Quote(
            instrument,
            bars[-1].close_price,
            ExchangeTradingCalendar().completed_close(instrument.market, target, now),
            snapshot.source + ":cached",
            previous_close=bars[-2].close_price if len(bars) > 1 else None,
        )
        return (
            quote,
            bars,
            (
                f"{instrument.symbol} 刷新失败，沿用 {target} 已保存收盘价；"
                f"来源 {snapshot.source}，抓取时间 {snapshot.fetched_at.isoformat()}。"
            ),
        )
    if cache is not None:
        try:
            await cache.save(ClosingPrices(instrument, quote.source, now, bars))
        except Exception:
            note += " 本次价格有效，但数据库缓存保存失败。"
    return quote, bars, note


async def _fetch_closing_quote_and_bars(instrument: Instrument, now: datetime):
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
