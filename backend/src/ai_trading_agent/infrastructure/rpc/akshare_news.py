"""Free public-news aggregation through AKShare.

The adapter intentionally labels the originating publisher and does not imply
that the public page data is licensed for execution decisions.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Iterable
from datetime import UTC, datetime, timedelta
from typing import Any

from ai_trading_agent.domain.aggregate.news import NewsArticle


class AkshareNewsProviderError(RuntimeError):
    """Raised when a configured public-news source cannot answer a query."""


NewsFetcher = Callable[[], Any]


class AkshareNewsProvider:
    """Read recent public market news without a Tushare news entitlement."""

    name = "akshare"

    def __init__(self, *, fetchers: dict[str, NewsFetcher] | None = None) -> None:
        self._fetchers = fetchers

    async def fetch_latest(
        self, *, sources: Iterable[str], lookback: timedelta
    ) -> list[NewsArticle]:
        source_names = tuple(source.strip().lower() for source in sources if source.strip())
        if not source_names:
            raise ValueError("at least one public news source is required")
        if lookback <= timedelta(0):
            raise ValueError("lookback must be positive")
        return await asyncio.to_thread(self._fetch_sync, source_names, lookback)

    def _fetch_sync(self, sources: tuple[str, ...], lookback: timedelta) -> list[NewsArticle]:
        now = datetime.now(UTC)
        articles: list[NewsArticle] = []
        for source in sources:
            frame = self._fetch_frame(source)
            if frame is None:
                continue
            try:
                rows = frame.to_dict(orient="records")
            except Exception as error:
                raise AkshareNewsProviderError(f"invalid response from {source}") from error
            articles.extend(_articles_from_rows(rows, source, now - lookback))
        return articles

    def _fetch_frame(self, source: str) -> Any:
        if self._fetchers is not None:
            fetcher = self._fetchers.get(source)
            if fetcher is None:
                raise AkshareNewsProviderError(f"unsupported public news source: {source}")
            try:
                return fetcher()
            except Exception as error:
                raise AkshareNewsProviderError(
                    f"news query failed for {source}: {error}"
                ) from error
        try:
            import akshare as ak
        except ImportError as error:  # pragma: no cover - deployment guard
            raise AkshareNewsProviderError(
                "AKShare is not installed; install the 'free-data' dependency group"
            ) from error
        fetchers: dict[str, NewsFetcher] = {
            "eastmoney": ak.stock_info_global_em,
            "sina": ak.stock_info_global_sina,
        }
        fetcher = fetchers.get(source)
        if fetcher is None:
            raise AkshareNewsProviderError(f"unsupported public news source: {source}")
        try:
            return fetcher()
        except Exception as error:
            raise AkshareNewsProviderError(f"news query failed for {source}: {error}") from error


def _articles_from_rows(
    rows: list[dict[str, object]], source: str, cutoff: datetime
) -> list[NewsArticle]:
    articles: list[NewsArticle] = []
    for row in rows:
        content = _text(row, "内容", "摘要", "content", "summary", "标题", "title")
        if not content:
            continue
        title = _text(row, "标题", "title") or content[:120]
        published_at = _published_at(row)
        if published_at is None or published_at < cutoff:
            continue
        articles.append(
            NewsArticle(
                title=title,
                content=content,
                publisher=_text(row, "文章来源", "source", "来源") or source,
                published_at=published_at,
                url=_text(row, "新闻链接", "链接", "url"),
            )
        )
    return articles


def _text(row: dict[str, object], *names: str) -> str | None:
    for name in names:
        value = row.get(name)
        if value is not None and str(value).strip().lower() not in {"", "nan", "none"}:
            return str(value).strip()
    return None


def _published_at(row: dict[str, object]) -> datetime | None:
    raw = _text(row, "发布时间", "时间", "datetime", "published_at")
    if raw is None:
        return None
    try:
        import pandas as pd

        value = pd.Timestamp(raw)
    except Exception:
        return None
    if value.tzinfo is None:
        return value.to_pydatetime().replace(tzinfo=UTC)
    return value.to_pydatetime().astimezone(UTC)
