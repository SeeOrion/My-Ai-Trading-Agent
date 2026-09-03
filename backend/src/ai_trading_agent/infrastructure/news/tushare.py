"""Tushare fast-finance-news adapter."""

from __future__ import annotations

import asyncio
from collections.abc import Iterable
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

from ai_trading_agent.domain.news import NewsArticle
from ai_trading_agent.infrastructure.market_data.config import TushareSettings


class TushareNewsProviderError(RuntimeError):
    """Raised when the configured Tushare news service cannot answer a query."""


class TushareNewsProvider:
    """Fetch licensed fast-news text from sources available to a Tushare account."""

    name = "tushare"

    def __init__(self, settings: TushareSettings) -> None:
        self._settings = settings

    async def fetch_latest(
        self, *, sources: Iterable[str], lookback: timedelta
    ) -> list[NewsArticle]:
        source_names = tuple(source.strip() for source in sources if source.strip())
        if not source_names:
            raise ValueError("at least one Tushare news source is required")
        if lookback <= timedelta(0):
            raise ValueError("lookback must be positive")
        return await asyncio.to_thread(self._fetch_sync, source_names, lookback)

    def _fetch_sync(self, sources: tuple[str, ...], lookback: timedelta) -> list[NewsArticle]:
        try:
            import tushare as ts
        except ImportError as error:  # pragma: no cover - deployment guard
            raise TushareNewsProviderError("Tushare SDK is not installed") from error
        now = datetime.now(UTC).astimezone(ZoneInfo("Asia/Shanghai"))
        start = now - lookback
        client = ts.pro_api(self._settings.token)
        articles: list[NewsArticle] = []
        for source in sources:
            try:
                frame = client.news(
                    src=source,
                    start_date=start.strftime("%Y-%m-%d %H:%M:%S"),
                    end_date=now.strftime("%Y-%m-%d %H:%M:%S"),
                )
            except Exception as error:
                raise TushareNewsProviderError(
                    f"news query failed for {source}: {error}"
                ) from error
            if frame is None:
                continue
            for _, row in frame.iterrows():
                articles.append(
                    NewsArticle(
                        title=str(row["title"]),
                        content=str(row["content"]),
                        publisher=source,
                        published_at=_parse_timestamp(row["datetime"]),
                    )
                )
        return articles


def _parse_timestamp(value: object) -> datetime:
    raw = str(value)
    for pattern in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"):
        try:
            return datetime.strptime(raw, pattern).replace(tzinfo=ZoneInfo("Asia/Shanghai"))
        except ValueError:
            continue
    raise TushareNewsProviderError(f"invalid Tushare news timestamp: {value!r}")
