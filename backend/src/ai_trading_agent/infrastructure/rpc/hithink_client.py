"""Shared private-key client for the documented Hithink Finance REST API."""

from __future__ import annotations

import asyncio
import json
from collections.abc import Mapping
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Protocol
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from ai_trading_agent.infrastructure.config.providers import HithinkFinanceSettings

_BASE_URL = "https://fuyao.aicubes.cn"


class HithinkFinanceServiceError(RuntimeError):
    """The upstream service could not provide a valid business response."""


class ResponseFetcher(Protocol):
    def __call__(self, url: str, api_key: str, timeout_seconds: float) -> bytes: ...


class HithinkFinanceRestClient:
    """Keep authentication, response-envelope validation and transport in one place."""

    def __init__(
        self,
        settings: HithinkFinanceSettings,
        *,
        response_fetcher: ResponseFetcher | None = None,
    ) -> None:
        self._settings = settings
        self._response_fetcher = response_fetcher or _download

    async def get(self, path: str, parameters: Mapping[str, object]) -> dict[str, object]:
        return await asyncio.to_thread(self.get_sync, path, parameters)

    def get_sync(self, path: str, parameters: Mapping[str, object]) -> dict[str, object]:
        query = urlencode({name: str(value) for name, value in parameters.items()})
        try:
            raw = self._response_fetcher(
                f"{_BASE_URL}{path}?{query}",
                self._settings.api_key,
                self._settings.timeout_seconds,
            )
            payload = json.loads(raw)
        except Exception as error:
            raise HithinkFinanceServiceError(f"request failed: {error}") from error
        if not isinstance(payload, dict):
            raise HithinkFinanceServiceError("response is not an object")
        if payload.get("code") != 0:
            raise HithinkFinanceServiceError(f"service error: {payload.get('message', 'unknown')}")
        data = payload.get("data")
        if not isinstance(data, dict):
            raise HithinkFinanceServiceError("successful response omitted data")
        return data


def _download(url: str, api_key: str, timeout_seconds: float) -> bytes:
    request = Request(
        url,
        headers={"X-api-key": api_key, "User-Agent": "MyAiTradingAgent/0.1"},
    )
    with urlopen(request, timeout=timeout_seconds) as response:  # noqa: S310 - fixed official host
        return response.read()


def response_items(data: Mapping[str, object]) -> list[dict[str, object]]:
    value = data.get("item")
    return [item for item in value if isinstance(item, dict)] if isinstance(value, list) else []


def decimal_or_none(value: object, field: str) -> Decimal | None:
    if value is None:
        return None
    try:
        result = Decimal(str(value))
    except Exception as error:
        raise HithinkFinanceServiceError(f"invalid {field}") from error
    if not result.is_finite():
        raise HithinkFinanceServiceError(f"invalid {field}")
    return result


def non_negative_decimal(value: object, field: str) -> Decimal:
    result = decimal_or_none(value, field)
    if result is None or result < 0:
        raise HithinkFinanceServiceError(f"invalid {field}")
    return result


def date_from_milliseconds(value: object, field: str) -> date | None:
    if value is None:
        return None
    try:
        return datetime.fromtimestamp(int(value) / 1000, tz=UTC).date()
    except (TypeError, ValueError, OSError) as error:
        raise HithinkFinanceServiceError(f"invalid {field}") from error


def datetime_from_milliseconds(value: object, field: str) -> datetime | None:
    if value is None:
        return None
    try:
        return datetime.fromtimestamp(int(value) / 1000, tz=UTC)
    except (TypeError, ValueError, OSError) as error:
        raise HithinkFinanceServiceError(f"invalid {field}") from error
