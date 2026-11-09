"""Free public-news aggregation through AKShare.

The adapter intentionally labels the originating publisher and does not imply
that the public page data is licensed for execution decisions.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Iterable
from datetime import UTC, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from ai_trading_agent.domain.aggregate.news import NewsArticle


class AkshareNewsProviderError(RuntimeError):
    """Raised when a configured public-news source cannot answer a query."""


NewsFetcher = Callable[[], Any]


class AkshareNewsProvider:
    """Read recent public market news without a Tushare news entitlement."""

    name = "akshare"

    def __init__(self, *, fetchers: dict[str, NewsFetcher] | None = None, timeout_seconds: float = 8) -> None:
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        self._fetchers = fetchers
        self._timeout_seconds = timeout_seconds
        self._pending: dict[str, asyncio.Task] = {}

    async def fetch_latest(
        self, *, sources: Iterable[str], lookback: timedelta
    ) -> list[NewsArticle]:
        source_names = tuple(source.strip().lower() for source in sources if source.strip())
        if not source_names:
            raise ValueError("at least one public news source is required")
        if lookback <= timedelta(0):
            raise ValueError("lookback must be positive")
        articles = []
        for source in source_names:
            task = self._pending.get(source)
            if task is None or task.done():
                task = asyncio.create_task(asyncio.to_thread(self._fetch_frame, source))
                # A timed-out thread cannot be killed. Keep it shared until it ends,
                # so repeated requests cannot accumulate unbounded worker threads.
                task.add_done_callback(lambda done: None if done.cancelled() else done.exception())
                self._pending[source] = task
            try:
                frame = await asyncio.wait_for(asyncio.shield(task), self._timeout_seconds)
            except TimeoutError as error:
                raise AkshareNewsProviderError(f"news query timed out for {source}") from error
            if frame is not None:
                articles.extend(_articles_from_rows(frame.to_dict(orient="records"), source, datetime.now(UTC) - lookback))
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
        if published_at is None or published_at < cutoff or published_at > datetime.now(UTC) + timedelta(minutes=5):
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
        if value is not None and str(value).strip().lower() not in {"", "nan", "nat", "none"}:
            return str(value).strip()
    return None


def _published_at(row: dict[str, object]) -> datetime | None:
    raw = _text(row, "发布时间", "时间", "datetime", "published_at")
    if raw is None:
        return None
    date = _text(row, "发布日期", "日期", "date")
    if date and len(raw) <= 8 and ":" in raw:
        raw = f"{date} {raw}"
    elif len(raw) <= 8 and ":" in raw:
        # A time without a date cannot safely be assigned to today's news.
        return None
    try:
        import pandas as pd

        value = pd.Timestamp(raw)
    except Exception:
        return None
    if value.tzinfo is None:
        return value.to_pydatetime().replace(tzinfo=ZoneInfo("Asia/Shanghai")).astimezone(UTC)
    return value.to_pydatetime().astimezone(UTC)
