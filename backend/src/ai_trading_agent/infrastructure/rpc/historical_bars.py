"""Historical daily OHLCV adapters used only by the technical-study context."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

from ai_trading_agent.domain.aggregate.market import Instrument
from ai_trading_agent.domain.aggregate.technical import PriceBar
from ai_trading_agent.domain.enums.market import Market
from ai_trading_agent.infrastructure.config.providers import FutuSettings, TushareSettings
from ai_trading_agent.infrastructure.rpc.futu_market import FutuSymbolMapper


class HistoricalBarsProviderError(RuntimeError):
    pass


class TushareHistoricalBarsProvider:
    name = "tushare"

    def __init__(self, settings: TushareSettings) -> None:
        self._settings = settings

    async def get_daily_bars(self, instrument: Instrument, limit: int) -> tuple[PriceBar, ...]:
        if instrument.market is not Market.A_SHARE:
            raise HistoricalBarsProviderError("Tushare historical bars only support A-share")
        return await asyncio.to_thread(self._get_daily_bars_sync, instrument, limit)

    def _get_daily_bars_sync(self, instrument: Instrument, limit: int) -> tuple[PriceBar, ...]:
        try:
            import tushare as ts
        except ImportError as error:  # pragma: no cover
            raise HistoricalBarsProviderError("Tushare SDK is not installed") from error
        today = datetime.now(UTC).astimezone(ZoneInfo("Asia/Shanghai")).date()
        frame = ts.pro_api(self._settings.token).daily(
            ts_code=instrument.symbol,
            start_date=(today - timedelta(days=limit * 3)).strftime("%Y%m%d"),
            end_date=today.strftime("%Y%m%d"),
            fields="trade_date,open,high,low,close,vol",
        )
        return _frame_to_bars(frame, instrument, limit)


class FutuHistoricalBarsProvider:
    name = "futu"

    def __init__(self, settings: FutuSettings) -> None:
        self._settings = settings

    async def get_daily_bars(self, instrument: Instrument, limit: int) -> tuple[PriceBar, ...]:
        if instrument.market not in {Market.HONG_KONG, Market.UNITED_STATES}:
            raise HistoricalBarsProviderError("Futu technical bars require Hong Kong or US market")
        return await asyncio.to_thread(self._get_daily_bars_sync, instrument, limit)

    def _get_daily_bars_sync(self, instrument: Instrument, limit: int) -> tuple[PriceBar, ...]:
        try:
            from futu import RET_OK, KLType, OpenQuoteContext
        except ImportError as error:  # pragma: no cover
            raise HistoricalBarsProviderError("Futu SDK is not installed") from error
        context = OpenQuoteContext(host=self._settings.host, port=self._settings.port)
        try:
            result, frame, _ = context.request_history_kline(
                FutuSymbolMapper.to_provider_code(instrument),
                ktype=KLType.K_DAY,
                max_count=limit,
            )
            if result != RET_OK:
                raise HistoricalBarsProviderError(f"Futu historical kline request failed: {frame}")
            return _frame_to_bars(frame, instrument, limit, date_column="time_key")
        finally:
            context.close()


def _frame_to_bars(
    frame: object, instrument: Instrument, limit: int, *, date_column: str = "trade_date"
) -> tuple[PriceBar, ...]:
    if frame is None or frame.empty:
        raise HistoricalBarsProviderError(f"no daily bars for {instrument.symbol}")
    rows: list[PriceBar] = []
    for _, row in frame.iterrows():
        raw_date = str(row[date_column])[:10].replace("-", "")
        try:
            session_date = datetime.strptime(raw_date, "%Y%m%d").date()
            rows.append(
                PriceBar(
                    instrument=instrument,
                    session_date=session_date,
                    open_price=_decimal(row["open"]),
                    high_price=_decimal(row["high"]),
                    low_price=_decimal(row["low"]),
                    close_price=_decimal(row["close"]),
                    volume=_decimal(row["volume"] if "volume" in row else row["vol"]),
                )
            )
        except (KeyError, ValueError) as error:
            raise HistoricalBarsProviderError(f"invalid historical bar: {error}") from error
    return tuple(sorted(rows, key=lambda bar: bar.session_date)[-limit:])


def _decimal(value: object) -> Decimal:
    try:
        result = Decimal(str(value))
    except Exception as error:
        raise HistoricalBarsProviderError(f"invalid numeric bar value: {value!r}") from error
    if not result.is_finite() or result < 0:
        raise HistoricalBarsProviderError(f"invalid numeric bar value: {value!r}")
    return result
