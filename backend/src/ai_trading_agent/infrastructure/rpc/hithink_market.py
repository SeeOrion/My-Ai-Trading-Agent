"""Private-key REST adapter for verified Hithink Finance A-share snapshots."""

from __future__ import annotations

import asyncio
import json
from collections.abc import Callable, Iterable
from datetime import UTC, datetime
from decimal import Decimal
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from ai_trading_agent.domain.aggregate.market import Instrument, Quote
from ai_trading_agent.domain.enums.market import InstrumentType, Market
from ai_trading_agent.infrastructure.config.providers import HithinkFinanceSettings


class HithinkFinanceProviderError(RuntimeError):
    pass


ResponseFetcher = Callable[[str, str, float], bytes]


class HithinkFinanceMarketDataProvider:
    """A-share equity snapshots; key stays in the request header only."""

    name = "hithink_finance"

    def __init__(
        self, settings: HithinkFinanceSettings, *, response_fetcher: ResponseFetcher | None = None
    ) -> None:
        self._settings = settings
        self._response_fetcher = response_fetcher or _download

    def supports(self, market: Market) -> bool:
        return market is Market.A_SHARE

    async def get_latest_quotes(self, instruments: Iterable[Instrument]) -> list[Quote]:
        requested = list(instruments)
        if any(
            item.market is not Market.A_SHARE or item.instrument_type is not InstrumentType.EQUITY
            for item in requested
        ):
            raise HithinkFinanceProviderError(
                "Hithink snapshot adapter currently supports A-share equities"
            )
        return await asyncio.to_thread(self._get_latest_quotes_sync, requested)

    def _get_latest_quotes_sync(self, instruments: list[Instrument]) -> list[Quote]:
        if not instruments:
            return []
        url = "https://fuyao.aicubes.cn/api/a-share/prices/snapshot?" + urlencode(
            {"thscodes": ",".join(item.symbol for item in instruments)}
        )
        try:
            payload = json.loads(
                self._response_fetcher(url, self._settings.api_key, self._settings.timeout_seconds)
            )
        except Exception as error:
            raise HithinkFinanceProviderError(f"snapshot request failed: {error}") from error
        if payload.get("code") != 0:
            raise HithinkFinanceProviderError(
                f"snapshot service error: {payload.get('message', 'unknown')}"
            )
        rows = {str(row.get("thscode")): row for row in payload.get("data", {}).get("item", [])}
        return [_quote(item, rows.get(item.symbol)) for item in instruments]


def _download(url: str, api_key: str, timeout_seconds: float) -> bytes:
    request = Request(url, headers={"X-api-key": api_key, "User-Agent": "MyAiTradingAgent/0.1"})
    with urlopen(request, timeout=timeout_seconds) as response:  # noqa: S310 - fixed official host
        return response.read()


def _quote(instrument: Instrument, row: object) -> Quote:
    if not isinstance(row, dict):
        raise HithinkFinanceProviderError(f"snapshot response omitted: {instrument.symbol}")
    return Quote(
        instrument=instrument,
        last_price=_decimal(row.get("last_price"), "last_price"),
        observed_at=datetime.now(UTC),
        source="hithink_finance",
        open_price=_optional_decimal(row.get("open_price"), "open_price"),
        high_price=_optional_decimal(row.get("high_price"), "high_price"),
        low_price=_optional_decimal(row.get("low_price"), "low_price"),
        previous_close=_optional_decimal(row.get("prev_price"), "prev_price"),
        volume=_optional_decimal(row.get("volume"), "volume"),
    )


def _decimal(value: object, field: str) -> Decimal:
    try:
        result = Decimal(str(value))
    except Exception as error:
        raise HithinkFinanceProviderError(f"invalid {field}") from error
    if not result.is_finite() or result < 0:
        raise HithinkFinanceProviderError(f"invalid {field}")
    return result


def _optional_decimal(value: object, field: str) -> Decimal | None:
    if value is None:
        return None
    return _decimal(value, field)
