"""Futu OpenD full-universe scanner for Hong Kong and US equities."""

from __future__ import annotations

import asyncio
from collections.abc import Iterator
from decimal import Decimal

from ai_trading_agent.domain.aggregate.market_scan import MarketScanBatch, MarketSnapshot
from ai_trading_agent.domain.enums.market import Market
from ai_trading_agent.infrastructure.config.providers import FutuSettings, MarketScanSettings
from ai_trading_agent.infrastructure.rpc.futu_market import (
    FutuMarketDataProvider,
    FutuProviderError,
    FutuSymbolMapper,
    _optional_decimal,
    _parse_futu_observed_at,
)


class FutuMarketScanner:
    """List a Futu market's equities, then request snapshots in bounded batches."""

    name = "futu"

    def __init__(self, settings: FutuSettings, scan_settings: MarketScanSettings) -> None:
        self._settings = settings
        self._scan_settings = scan_settings

    async def scan_market(self, market: Market) -> MarketScanBatch:
        if market not in {Market.HONG_KONG, Market.UNITED_STATES}:
            raise FutuProviderError(
                "Futu full-market scanner only supports Hong Kong and US equities"
            )
        return await asyncio.to_thread(self._scan_market_sync, market)

    def _scan_market_sync(self, market: Market) -> MarketScanBatch:
        try:
            from futu import RET_OK, OpenQuoteContext, SecurityType
            from futu import Market as FutuMarket
        except ImportError as error:  # pragma: no cover - deployment guard
            raise FutuProviderError(
                "Futu SDK is not installed; install the 'futu' optional dependency"
            ) from error

        futu_market = {
            Market.HONG_KONG: FutuMarket.HK,
            Market.UNITED_STATES: FutuMarket.US,
        }[market]
        FutuMarketDataProvider(self._settings)._ensure_gateway_is_reachable()
        context = OpenQuoteContext(host=self._settings.host, port=self._settings.port)
        try:
            result_code, basic_frame = context.get_stock_basicinfo(futu_market, SecurityType.STOCK)
            if result_code != RET_OK:
                raise FutuProviderError(f"stock list request failed: {basic_frame}")
            eligible_frame = _eligible_equities(basic_frame, market)
            provider_codes = [str(code) for code in eligible_frame["code"].tolist()]
            names = {
                str(row["code"]): str(row.get("name") or str(row["code"]))
                for _, row in eligible_frame.iterrows()
            }
            snapshots: list[MarketSnapshot] = []
            for codes in _chunks(provider_codes, self._scan_settings.futu_batch_size):
                snapshots.extend(
                    _read_supported_snapshot_batch(context, codes, market, names, RET_OK)
                )
            if not snapshots:
                raise FutuProviderError("no Futu snapshots were available for this market")
            return MarketScanBatch(
                market=market,
                source=self.name,
                universe_size=len(provider_codes),
                snapshots=tuple(snapshots),
            )
        finally:
            context.close()


def _chunks(values: list[str], size: int) -> Iterator[list[str]]:
    for start in range(0, len(values), size):
        yield values[start : start + size]


def _eligible_equities(frame: object, market: Market):  # type: ignore[no-untyped-def]
    """Exclude Futu US OTC symbols, which its snapshot endpoint rejects."""
    if market is not Market.UNITED_STATES:
        return frame
    if "exchange_type" not in frame.columns:
        return frame
    return frame[~frame["exchange_type"].isin(["US_PINK", "N/A"])]


def _read_supported_snapshot_batch(
    context: object,
    codes: list[str],
    market: Market,
    names: dict[str, str],
    success_code: object,
) -> list[MarketSnapshot]:
    """Split a rejected batch so one unsupported OTC/security cannot stop a scan."""
    snapshot_code, frame = context.get_market_snapshot(codes)
    if snapshot_code == success_code:
        return _snapshots_from_frame(frame, market, names)
    if len(codes) == 1:
        return []
    midpoint = len(codes) // 2
    return _read_supported_snapshot_batch(
        context, codes[:midpoint], market, names, success_code
    ) + _read_supported_snapshot_batch(context, codes[midpoint:], market, names, success_code)


def _snapshots_from_frame(
    frame: object, market: Market, names: dict[str, str]
) -> list[MarketSnapshot]:
    snapshots: list[MarketSnapshot] = []
    for _, row in frame.iterrows():
        try:
            code = str(row["code"])
            instrument = FutuSymbolMapper.from_provider_code(code, market)
            last_price = _decimal(row["last_price"], "last_price")
            previous_close = _optional_decimal(row.get("prev_close_price"), "prev_close_price")
            snapshots.append(
                MarketSnapshot(
                    instrument=instrument,
                    name=str(row.get("name") or names.get(code) or instrument.symbol),
                    observed_at=_parse_futu_observed_at(
                        str(row["update_time"]).split(" ", maxsplit=1)[0],
                        str(row["update_time"]).split(" ", maxsplit=1)[-1],
                        market,
                    ),
                    source="futu",
                    last_price=last_price,
                    previous_close=previous_close,
                    open_price=_optional_decimal(row.get("open_price"), "open_price"),
                    high_price=_optional_decimal(row.get("high_price"), "high_price"),
                    low_price=_optional_decimal(row.get("low_price"), "low_price"),
                    volume=_optional_decimal(row.get("volume"), "volume"),
                    turnover=_optional_decimal(row.get("turnover"), "turnover"),
                    change_percent=_change_percent(last_price, previous_close),
                    price_to_earnings=_optional_decimal(row.get("pe_ratio"), "pe_ratio"),
                    price_to_book=_optional_decimal(row.get("pb_ratio"), "pb_ratio"),
                )
            )
        except (KeyError, ValueError, FutuProviderError):
            continue
    return snapshots


def _decimal(value: object, field: str) -> Decimal:
    parsed = _optional_decimal(value, field)
    if parsed is None or parsed < 0:
        raise FutuProviderError(f"invalid {field}: {value!r}")
    return parsed


def _change_percent(last_price: Decimal, previous_close: Decimal | None) -> Decimal | None:
    if previous_close is None or previous_close == 0:
        return None
    return (last_price - previous_close) * Decimal("100") / previous_close
