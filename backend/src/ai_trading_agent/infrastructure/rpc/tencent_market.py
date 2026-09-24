"""Experimental no-credential public quote adapter for Tencent's page feed."""

from __future__ import annotations

import asyncio
import re
import time
from collections.abc import Callable, Iterable
from datetime import UTC, datetime
from decimal import Decimal
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

from ai_trading_agent.application.candidates import research_universe
from ai_trading_agent.domain.aggregate.candidate import CandidateObservation
from ai_trading_agent.domain.aggregate.market import Instrument, Quote
from ai_trading_agent.domain.enums.market import Market
from ai_trading_agent.infrastructure.config.providers import TencentQuoteSettings


class TencentQuoteProviderError(RuntimeError):
    """Raised when the public page feed cannot return a usable quote."""


ResponseFetcher = Callable[[str, float], bytes]
Sleeper = Callable[[float], None]


class TencentQuoteMarketDataProvider:
    """Adapt public Tencent page quotes into the provider-neutral quote contract.

    This uncredentialed endpoint is an experimental research/display source. No
    automatic order or discipline action may rely on it.
    """

    name = "tencent_public"

    def __init__(
        self,
        settings: TencentQuoteSettings,
        *,
        response_fetcher: ResponseFetcher | None = None,
        sleeper: Sleeper = time.sleep,
    ) -> None:
        self._settings = settings
        self._response_fetcher = response_fetcher or _download_quote_payload
        self._sleeper = sleeper

    def supports(self, market: Market) -> bool:
        return market in {Market.A_SHARE, Market.HONG_KONG, Market.UNITED_STATES}

    async def get_latest_quotes(self, instruments: Iterable[Instrument]) -> list[Quote]:
        requested = list(instruments)
        if any(not self.supports(instrument.market) for instrument in requested):
            raise TencentQuoteProviderError(
                "Tencent public quote adapter does not support this market"
            )
        if not requested:
            return []
        return await asyncio.to_thread(self._get_latest_quotes_sync, requested)

    async def get_candidate_observations(self, market: Market) -> list[CandidateObservation]:
        """Read one documented liquid-stock research universe for a market."""
        if not self.supports(market):
            raise TencentQuoteProviderError(f"unsupported market: {market.value}")
        instruments = list(research_universe(market))
        return await asyncio.to_thread(self._get_candidate_observations_sync, instruments)

    def _get_latest_quotes_sync(self, instruments: list[Instrument]) -> list[Quote]:
        codes = [_to_provider_code(instrument) for instrument in instruments]
        url = f"https://qt.gtimg.cn/q={','.join(codes)}"
        payload = self._fetch_payload(url)
        rows_by_code = _parse_payload(payload)
        quotes: list[Quote] = []
        for instrument, code in zip(instruments, codes, strict=True):
            fields = rows_by_code.get(code)
            if fields is None:
                raise TencentQuoteProviderError(f"quote response omitted: {instrument.symbol}")
            quotes.append(_to_quote(instrument, fields))
        return quotes

    def _get_candidate_observations_sync(
        self, instruments: list[Instrument]
    ) -> list[CandidateObservation]:
        codes = [_to_provider_code(instrument) for instrument in instruments]
        url = f"https://qt.gtimg.cn/q={','.join(codes)}"
        payload = self._fetch_payload(url)
        rows_by_code = _parse_payload(payload)
        observations: list[CandidateObservation] = []
        for instrument, code in zip(instruments, codes, strict=True):
            fields = rows_by_code.get(code)
            if fields is None:
                continue
            try:
                quote = _to_quote(instrument, fields)
                observations.append(
                    CandidateObservation(
                        instrument=instrument,
                        name=fields[1].strip() or instrument.symbol,
                        last_price=quote.last_price,
                        change_percent=_optional_signed_decimal(fields, 32, "change percent"),
                        turnover=_optional_decimal(fields, 37, "turnover"),
                        high_price=quote.high_price,
                        low_price=quote.low_price,
                        observed_at=quote.observed_at,
                        source=quote.source,
                    )
                )
            except (IndexError, ValueError, TencentQuoteProviderError):
                continue
        if not observations:
            raise TencentQuoteProviderError(
                "public quote response did not contain usable candidates"
            )
        return observations

    def _fetch_payload(self, url: str) -> str:
        last_error: Exception | None = None
        for attempt in range(1, self._settings.max_attempts + 1):
            try:
                return self._response_fetcher(url, self._settings.timeout_seconds).decode(
                    "gbk", errors="replace"
                )
            except Exception as error:
                last_error = error
                if attempt < self._settings.max_attempts:
                    self._sleeper(
                        self._settings.retry_base_delay_seconds * (2 ** (attempt - 1))
                    )
        raise TencentQuoteProviderError(
            f"quote query failed after {self._settings.max_attempts} attempts: {last_error}"
        ) from last_error


def _download_quote_payload(url: str, timeout_seconds: float) -> bytes:
    request = Request(url, headers={"User-Agent": "Mozilla/5.0 (MyAiTradingAgent/0.1)"})
    with urlopen(request, timeout=timeout_seconds) as response:  # noqa: S310 - fixed public endpoint
        return response.read()


def _to_provider_code(instrument: Instrument) -> str:
    if instrument.market is Market.A_SHARE:
        try:
            number, exchange = instrument.symbol.rsplit(".", maxsplit=1)
        except ValueError as error:
            raise TencentQuoteProviderError(
                "A-share symbols must use 6 digits followed by .SH or .SZ"
            ) from error
        if not number.isdigit() or len(number) != 6 or exchange not in {"SH", "SZ"}:
            raise TencentQuoteProviderError(
                "A-share symbols must use 6 digits followed by .SH or .SZ"
            )
        return f"{exchange.lower()}{number}"
    if instrument.market is Market.HONG_KONG:
        number = instrument.symbol.removesuffix(".HK")
        if not number.isdigit() or len(number) > 5:
            raise TencentQuoteProviderError("Hong Kong symbols must use up to five digits or .HK")
        return f"hk{number.zfill(5)}"
    if instrument.market is Market.UNITED_STATES:
        symbol = instrument.symbol.split(".", maxsplit=1)[0]
        if not symbol.replace("-", "").isalnum():
            raise TencentQuoteProviderError("US symbols must be alphanumeric tickers")
        return f"us{symbol}"
    raise TencentQuoteProviderError(f"unsupported market: {instrument.market.value}")


def _parse_payload(payload: str) -> dict[str, list[str]]:
    results: dict[str, list[str]] = {}
    for provider_code, fields in re.findall(r'v_([^=]+)="([^"]*)"', payload):
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
        for pattern in ("%Y%m%d%H%M%S", "%Y/%m/%d %H:%M:%S", "%Y-%m-%d %H:%M:%S"):
            try:
                return datetime.strptime(fields[30], pattern).replace(
                    tzinfo=ZoneInfo("Asia/Shanghai")
                ).astimezone(UTC)
            except ValueError:
                continue
    return datetime.now(UTC)


def _optional_decimal(fields: list[str], index: int, label: str) -> Decimal | None:
    if index >= len(fields) or fields[index].strip() in {"", "-"}:
        return None
    return _decimal(fields[index], label)


def _optional_signed_decimal(fields: list[str], index: int, label: str) -> Decimal | None:
    if index >= len(fields) or fields[index].strip() in {"", "-"}:
        return None
    try:
        result = Decimal(fields[index])
    except Exception as error:
        raise TencentQuoteProviderError(f"invalid {label}: {fields[index]!r}") from error
    if not result.is_finite():
        raise TencentQuoteProviderError(f"invalid {label}: {fields[index]!r}")
    return result


def _decimal(value: str, label: str) -> Decimal:
    try:
        result = Decimal(value)
    except Exception as error:
        raise TencentQuoteProviderError(f"invalid {label}: {value!r}") from error
    if not result.is_finite() or result < 0:
        raise TencentQuoteProviderError(f"invalid {label}: {value!r}")
    return result
