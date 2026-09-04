"""Experimental no-credential A-share quote adapter for Tencent's public page feed."""

from __future__ import annotations

import asyncio
import re
from collections.abc import Callable, Iterable
from datetime import UTC, datetime
from decimal import Decimal
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

from ai_trading_agent.domain.aggregate.market import Instrument, Quote
from ai_trading_agent.domain.enums.market import Market
from ai_trading_agent.infrastructure.config.providers import TencentQuoteSettings


class TencentQuoteProviderError(RuntimeError):
    """Raised when the public page feed cannot return a usable A-share quote."""


ResponseFetcher = Callable[[str, float], bytes]


class TencentQuoteMarketDataProvider:
    """Adapt public Tencent page quotes into the provider-neutral quote contract.

    This uncredentialed endpoint is an experimental research/display fallback;
    no automatic order or discipline action may rely on it.
    """

    name = "tencent_public"

    def __init__(
        self,
        settings: TencentQuoteSettings,
        *,
        response_fetcher: ResponseFetcher | None = None,
    ) -> None:
        self._settings = settings
        self._response_fetcher = response_fetcher or _download_quote_payload

    def supports(self, market: Market) -> bool:
        return market is Market.A_SHARE

    async def get_latest_quotes(self, instruments: Iterable[Instrument]) -> list[Quote]:
        requested = list(instruments)
        if any(instrument.market is not Market.A_SHARE for instrument in requested):
            raise TencentQuoteProviderError("Tencent public quote adapter only supports A-share")
        if not requested:
            return []
        return await asyncio.to_thread(self._get_latest_quotes_sync, requested)

    def _get_latest_quotes_sync(self, instruments: list[Instrument]) -> list[Quote]:
        codes = [_to_provider_code(instrument) for instrument in instruments]
        url = f"https://qt.gtimg.cn/q={','.join(codes)}"
        try:
            payload = self._response_fetcher(url, self._settings.timeout_seconds).decode(
                "gbk", errors="replace"
            )
        except Exception as error:
            raise TencentQuoteProviderError(f"quote query failed: {error}") from error
        rows_by_code = _parse_payload(payload)
        quotes: list[Quote] = []
        for instrument, code in zip(instruments, codes, strict=True):
            fields = rows_by_code.get(code)
            if fields is None:
                raise TencentQuoteProviderError(f"quote response omitted: {instrument.symbol}")
            quotes.append(_to_quote(instrument, fields))
        return quotes


def _download_quote_payload(url: str, timeout_seconds: float) -> bytes:
    request = Request(url, headers={"User-Agent": "Mozilla/5.0 (MyAiTradingAgent/0.1)"})
    with urlopen(request, timeout=timeout_seconds) as response:  # noqa: S310 - fixed public endpoint
        return response.read()


def _to_provider_code(instrument: Instrument) -> str:
    try:
        number, exchange = instrument.symbol.rsplit(".", maxsplit=1)
    except ValueError as error:
        raise TencentQuoteProviderError(
            "A-share symbols must use 6 digits followed by .SH or .SZ"
        ) from error
    if not number.isdigit() or len(number) != 6 or exchange not in {"SH", "SZ"}:
        raise TencentQuoteProviderError("A-share symbols must use 6 digits followed by .SH or .SZ")
    return f"{exchange.lower()}{number}"


def _parse_payload(payload: str) -> dict[str, list[str]]:
    results: dict[str, list[str]] = {}
    for provider_code, fields in re.findall(r'v_([a-z]{2}\d{6})="([^"]*)"', payload):
        values = fields.split("~")
        if len(values) >= 6:
            results[provider_code] = values
    if not results:
        raise TencentQuoteProviderError("invalid public quote response")
    return results


def _to_quote(instrument: Instrument, fields: list[str]) -> Quote:
    return Quote(
        instrument=instrument,
        last_price=_decimal(fields[3], "last price"),
        observed_at=_observed_at(fields),
        source="tencent_public",
        open_price=_optional_decimal(fields, 5, "open price"),
        high_price=_optional_decimal(fields, 33, "high price"),
        low_price=_optional_decimal(fields, 34, "low price"),
        previous_close=_optional_decimal(fields, 4, "previous close"),
        volume=_optional_decimal(fields, 6, "volume"),
    )


def _observed_at(fields: list[str]) -> datetime:
    if len(fields) > 30:
        try:
            return datetime.strptime(fields[30], "%Y%m%d%H%M%S").replace(
                tzinfo=ZoneInfo("Asia/Shanghai")
            ).astimezone(UTC)
        except ValueError:
            pass
    return datetime.now(UTC)


def _optional_decimal(fields: list[str], index: int, label: str) -> Decimal | None:
    if index >= len(fields) or fields[index].strip() in {"", "-"}:
        return None
    return _decimal(fields[index], label)


def _decimal(value: str, label: str) -> Decimal:
    try:
        result = Decimal(value)
    except Exception as error:
        raise TencentQuoteProviderError(f"invalid {label}: {value!r}") from error
    if not result.is_finite() or result < 0:
        raise TencentQuoteProviderError(f"invalid {label}: {value!r}")
    return result
