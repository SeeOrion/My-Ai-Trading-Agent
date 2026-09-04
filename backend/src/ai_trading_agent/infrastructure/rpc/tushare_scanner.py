"""Tushare end-of-day full A-share scanner using daily and daily_basic."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

from ai_trading_agent.domain.aggregate.market import Instrument
from ai_trading_agent.domain.aggregate.market_scan import MarketScanBatch, MarketSnapshot
from ai_trading_agent.domain.enums.market import Market
from ai_trading_agent.infrastructure.config.providers import TushareSettings
from ai_trading_agent.infrastructure.rpc.tushare_market import TushareProviderError, _market_close


class TushareMarketScanner:
    """Read one completed A-share trading day and its daily valuation fields."""

    name = "tushare_daily_basic"

    def __init__(self, settings: TushareSettings, *, lookback_days: int = 10) -> None:
        if lookback_days < 1:
            raise ValueError("lookback_days must be positive")
        self._settings = settings
        self._lookback_days = lookback_days

    async def scan_market(self, market: Market) -> MarketScanBatch:
        if market is not Market.A_SHARE:
            raise TushareProviderError("Tushare full-market scanner only supports A shares")
        return await asyncio.to_thread(self._scan_market_sync)

    def _scan_market_sync(self) -> MarketScanBatch:
        try:
            import tushare as ts
        except ImportError as error:  # pragma: no cover - deployment guard
            raise TushareProviderError("Tushare SDK is not installed") from error
        client = ts.pro_api(self._settings.token)
        try:
            basics = client.stock_basic(
                exchange="",
                list_status="L",
                fields="ts_code,name",
            )
        except Exception as error:
            raise TushareProviderError(f"stock universe query failed: {error}") from error
        if basics is None or basics.empty:
            raise TushareProviderError("no listed A-share securities returned")
        daily, valuations, trade_date = self._latest_completed_day(client)
        names = {str(row["ts_code"]): str(row["name"]) for _, row in basics.iterrows()}
        valuation_rows = {
            str(row["ts_code"]): row for _, row in valuations.iterrows()
        }
        snapshots: list[MarketSnapshot] = []
        for _, row in daily.iterrows():
            try:
                code = str(row["ts_code"])
                last_price = _decimal(row["close"], "close")
                previous_close = _decimal(row["pre_close"], "pre_close")
                valuation = valuation_rows.get(code)
                snapshots.append(
                    MarketSnapshot(
                        instrument=Instrument(code, Market.A_SHARE),
                        name=names.get(code, code),
                        observed_at=_market_close(trade_date),
                        source=self.name,
                        last_price=last_price,
                        previous_close=previous_close,
                        open_price=_decimal(row["open"], "open"),
                        high_price=_decimal(row["high"], "high"),
                        low_price=_decimal(row["low"], "low"),
                        volume=_decimal(row["vol"], "vol"),
                        turnover=_decimal(row["amount"], "amount") * Decimal("1000"),
                        change_percent=_optional_decimal(row.get("pct_chg"), "pct_chg"),
                        price_to_earnings=_optional_decimal(
                            None if valuation is None else valuation.get("pe"), "pe"
                        ),
                        price_to_book=_optional_decimal(
                            None if valuation is None else valuation.get("pb"), "pb"
                        ),
                    )
                )
            except (ValueError, TushareProviderError):
                continue
        return MarketScanBatch(
            market=Market.A_SHARE,
            source=self.name,
            universe_size=len(basics),
            snapshots=tuple(snapshots),
        )

    def _latest_completed_day(self, client: object):  # type: ignore[no-untyped-def]
        today = datetime.now(UTC).astimezone(ZoneInfo("Asia/Shanghai")).date()
        for offset in range(self._lookback_days):
            trade_date = (today - timedelta(days=offset)).strftime("%Y%m%d")
            try:
                daily = client.daily(
                    trade_date=trade_date,
                    fields="ts_code,trade_date,open,high,low,close,pre_close,pct_chg,vol,amount",
                )
            except Exception as error:
                raise TushareProviderError(f"daily query failed: {error}") from error
            if daily is None or daily.empty:
                continue
            try:
                valuations = client.daily_basic(
                    trade_date=trade_date,
                    fields="ts_code,trade_date,pe,pb",
                )
            except Exception as error:
                raise TushareProviderError(f"daily_basic query failed: {error}") from error
            if valuations is None:
                raise TushareProviderError("daily_basic returned no data")
            return daily, valuations, trade_date
        raise TushareProviderError("no recent completed A-share trading day found")


def _decimal(value: object, field: str) -> Decimal:
    try:
        parsed = Decimal(str(value))
    except Exception as error:
        raise TushareProviderError(f"invalid {field}: {value!r}") from error
    if not parsed.is_finite() or parsed < 0:
        raise TushareProviderError(f"invalid {field}: {value!r}")
    return parsed


def _optional_decimal(value: object, field: str) -> Decimal | None:
    if value is None or str(value).lower() in {"", "nan", "none"}:
        return None
    try:
        parsed = Decimal(str(value))
    except Exception as error:
        raise TushareProviderError(f"invalid {field}: {value!r}") from error
    if not parsed.is_finite():
        raise TushareProviderError(f"invalid {field}: {value!r}")
    return parsed
