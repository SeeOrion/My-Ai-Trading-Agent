"""Futu OpenAPI adapter for subscribed real-time stock and ETF quotes."""

from __future__ import annotations

import asyncio
from collections.abc import Iterable
from datetime import UTC, datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

from ai_trading_agent.domain.market import Instrument, InstrumentType, Market, Quote
from ai_trading_agent.infrastructure.market_data.config import FutuSettings


class FutuProviderError(RuntimeError):
    """Raised when Futu OpenD or its Python SDK cannot satisfy a request."""


class FutuMarketDataProvider:
    """Fetch one-off real-time quote snapshots from a local Futu OpenD gateway.

    The official SDK is synchronous, so its calls run in a worker thread. This
    adapter subscribes with ``subscribe_push=False``, reads the snapshot and
    always closes the OpenD context; it does not own a long-lived stream.
    """

    name = "futu"

    def __init__(self, settings: FutuSettings) -> None:
        self._settings = settings

    def supports(self, market: Market) -> bool:
        return market in {Market.A_SHARE, Market.HONG_KONG, Market.UNITED_STATES}

    async def get_latest_quotes(self, instruments: Iterable[Instrument]) -> list[Quote]:
        requested = list(instruments)
        if not requested:
            return []
        unsupported = [
            instrument.market.value
            for instrument in requested
            if not self.supports(instrument.market)
        ]
        if unsupported:
            raise FutuProviderError(f"unsupported market(s): {', '.join(unsupported)}")
        return await asyncio.to_thread(self._get_latest_quotes_sync, requested)

    def _get_latest_quotes_sync(self, instruments: list[Instrument]) -> list[Quote]:
        try:
            from futu import RET_OK, OpenQuoteContext, SubType
        except ImportError as error:  # pragma: no cover - exercised by deployment configuration
            raise FutuProviderError(
                "Futu SDK is not installed; install the 'futu' optional dependency"
            ) from error

        provider_codes = [
            FutuSymbolMapper.to_provider_code(instrument) for instrument in instruments
        ]
        context = OpenQuoteContext(host=self._settings.host, port=self._settings.port)
        try:
            subscribe_code, subscribe_result = context.subscribe(
                provider_codes,
                [SubType.QUOTE],
                subscribe_push=False,
            )
            if subscribe_code != RET_OK:
                raise FutuProviderError(f"quote subscription failed: {subscribe_result}")
            result_code, frame = context.get_stock_quote(provider_codes)
            if result_code != RET_OK:
                raise FutuProviderError(f"quote request failed: {frame}")
            by_code = {str(row["code"]): row for _, row in frame.iterrows()}
            missing = [code for code in provider_codes if code not in by_code]
            if missing:
                raise FutuProviderError(f"quote response omitted: {', '.join(missing)}")
            return [
                self._to_quote(instrument, by_code[code])
                for instrument, code in zip(instruments, provider_codes, strict=True)
            ]
        finally:
            context.close()

    @staticmethod
    def _to_quote(instrument: Instrument, row: object) -> Quote:
        # Pandas Series supports bracket indexing; keeping the boundary local
        # avoids importing pandas in the domain model.
        observed_at = _parse_futu_observed_at(
            str(row["data_date"]), str(row["data_time"]), instrument.market
        )
        return Quote(
            instrument=instrument,
            last_price=_decimal(row["last_price"], "last_price"),
            observed_at=observed_at,
            source="futu",
            open_price=_optional_decimal(row.get("open_price"), "open_price"),
            high_price=_optional_decimal(row.get("high_price"), "high_price"),
            low_price=_optional_decimal(row.get("low_price"), "low_price"),
            previous_close=_optional_decimal(row.get("prev_close_price"), "prev_close_price"),
            volume=_optional_decimal(row.get("volume"), "volume"),
        )


class FutuSymbolMapper:
    """Translate canonical project symbols to documented Futu stock codes."""

    @staticmethod
    def to_provider_code(instrument: Instrument) -> str:
        if instrument.instrument_type is InstrumentType.OPTION:
            # Option codes carry venue-specific contract terms. Silently
            # guessing them would risk returning a quote for another contract.
            if instrument.symbol.startswith("US."):
                return instrument.symbol
            raise ValueError("US option symbols must use an explicit Futu US.* contract code")
        if instrument.market is Market.UNITED_STATES:
            return f"US.{instrument.symbol}"
        if instrument.market is Market.HONG_KONG:
            number = instrument.symbol.removesuffix(".HK")
            if not number.isdigit() or len(number) > 5:
                raise ValueError(f"invalid Hong Kong symbol: {instrument.symbol}")
            return f"HK.{number.zfill(5)}"
        if instrument.market is Market.A_SHARE:
            try:
                number, exchange = instrument.symbol.rsplit(".", maxsplit=1)
            except ValueError as error:
                raise ValueError(
                    "A-share symbols must use 6 digits followed by .SH or .SZ"
                ) from error
            if not number.isdigit() or len(number) != 6 or exchange not in {"SH", "SZ"}:
                raise ValueError("A-share symbols must use 6 digits followed by .SH or .SZ")
            return f"{exchange}.{number}"
        raise ValueError(f"unsupported market: {instrument.market.value}")


def _parse_futu_observed_at(date_value: str, time_value: str, market: Market) -> datetime:
    timezone = (
        ZoneInfo("America/New_York")
        if market is Market.UNITED_STATES
        else ZoneInfo("Asia/Shanghai")
    )
    raw = f"{date_value} {time_value}"
    for pattern in ("%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(raw, pattern).replace(tzinfo=timezone).astimezone(UTC)
        except ValueError:
            continue
    raise FutuProviderError(f"invalid Futu quote timestamp: {raw}")


def _decimal(value: object, field: str) -> Decimal:
    try:
        parsed = Decimal(str(value))
    except Exception as error:
        raise FutuProviderError(f"invalid {field}: {value!r}") from error
    if not parsed.is_finite():
        raise FutuProviderError(f"invalid {field}: {value!r}")
    return parsed


def _optional_decimal(value: object, field: str) -> Decimal | None:
    if value is None or str(value).lower() in {"", "nan", "none"}:
        return None
    return _decimal(value, field)
