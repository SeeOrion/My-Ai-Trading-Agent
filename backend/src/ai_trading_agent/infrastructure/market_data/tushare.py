"""Tushare Pro adapter for the most recent available A-share daily bar."""

from __future__ import annotations

import asyncio
from collections.abc import Iterable
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

from ai_trading_agent.domain.market import Instrument, Market, Quote
from ai_trading_agent.infrastructure.market_data.config import TushareSettings


class TushareProviderError(RuntimeError):
    """Raised when Tushare cannot provide a valid latest daily observation."""


class TushareMarketDataProvider:
    """Adapt Tushare's A-share daily endpoint into a provider-neutral quote.

    Tushare's ``daily`` endpoint is end-of-day data, not intraday real-time
    data. The returned quote is stamped at the Asia/Shanghai market close so
    the application's freshness policy can never mislabel it as live.
    """

    name = "tushare"

    def __init__(self, settings: TushareSettings, *, lookback_days: int = 10) -> None:
        if lookback_days < 1:
            raise ValueError("lookback_days must be positive")
        self._settings = settings
        self._lookback_days = lookback_days

    def supports(self, market: Market) -> bool:
        return market is Market.A_SHARE

    async def get_latest_quotes(self, instruments: Iterable[Instrument]) -> list[Quote]:
        requested = list(instruments)
        if any(instrument.market is not Market.A_SHARE for instrument in requested):
            raise TushareProviderError("Tushare quote adapter only supports A-share instruments")
        return await asyncio.to_thread(self._get_latest_quotes_sync, requested)

    def _get_latest_quotes_sync(self, instruments: list[Instrument]) -> list[Quote]:
        try:
            import tushare as ts
        except ImportError as error:  # pragma: no cover - exercised by deployment configuration
            raise TushareProviderError(
                "Tushare SDK is not installed; install the 'tushare' optional dependency"
            ) from error

        client = ts.pro_api(self._settings.token)
        today = datetime.now(UTC).astimezone(ZoneInfo("Asia/Shanghai")).date()
        start = (today - timedelta(days=self._lookback_days)).strftime("%Y%m%d")
        end = today.strftime("%Y%m%d")
        return [self._get_one(client, instrument, start, end) for instrument in instruments]

    @staticmethod
    def _get_one(client: object, instrument: Instrument, start: str, end: str) -> Quote:
        try:
            frame = client.daily(
                ts_code=instrument.symbol,
                start_date=start,
                end_date=end,
                fields="ts_code,trade_date,open,high,low,close,pre_close,vol",
            )
        except Exception as error:
            raise TushareProviderError(
                f"daily query failed for {instrument.symbol}: {error}"
            ) from error
        if frame is None or frame.empty:
            raise TushareProviderError(f"no daily data returned for {instrument.symbol}")
        row = frame.sort_values("trade_date", ascending=False).iloc[0]
        return Quote(
            instrument=instrument,
            last_price=_decimal(row["close"], "close"),
            observed_at=_market_close(str(row["trade_date"])),
            source="tushare",
            open_price=_decimal(row["open"], "open"),
            high_price=_decimal(row["high"], "high"),
            low_price=_decimal(row["low"], "low"),
            previous_close=_decimal(row["pre_close"], "pre_close"),
            volume=_decimal(row["vol"], "vol"),
        )


def _market_close(trade_date: str) -> datetime:
    try:
        parsed_date = date.fromisoformat(f"{trade_date[:4]}-{trade_date[4:6]}-{trade_date[6:8]}")
    except ValueError as error:
        raise TushareProviderError(f"invalid trade_date: {trade_date!r}") from error
    close_at = datetime.combine(parsed_date, time(15, 0), tzinfo=ZoneInfo("Asia/Shanghai"))
    return close_at.astimezone(UTC)


def _decimal(value: object, field: str) -> Decimal:
    try:
        parsed = Decimal(str(value))
    except Exception as error:
        raise TushareProviderError(f"invalid {field}: {value!r}") from error
    if not parsed.is_finite() or parsed < 0:
        raise TushareProviderError(f"invalid {field}: {value!r}")
    return parsed
