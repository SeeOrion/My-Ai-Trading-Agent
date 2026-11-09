import asyncio
from datetime import UTC, datetime, timedelta
from threading import Event
from unittest.mock import AsyncMock

import pandas as pd
import pytest

from ai_trading_agent.application.news import ResilientLatestNewsHandler, NewsCollectionUnavailableError
from ai_trading_agent.domain.aggregate.news import NewsArticle
from ai_trading_agent.infrastructure.rpc.akshare_news import AkshareNewsProvider, _published_at


def test_china_time_and_split_date_are_converted_to_utc():
    expected = datetime(2026, 11, 9, 2, 30, tzinfo=UTC)
    assert _published_at({"发布时间": "2026-11-09 10:30:00"}) == expected
    assert _published_at({"发布日期": "2026-11-09", "发布时间": "10:30:00"}) == expected
    assert _published_at({"时间": "10:30:00"}) is None
    assert _published_at({"时间": "NaT"}) is None


@pytest.mark.asyncio
async def test_timeout_falls_back_without_spawning_more_blocked_threads():
    release = Event()
    calls = []
    now = datetime.now(UTC)
    def blocked():
        calls.append("eastmoney")
        release.wait(2)
        return pd.DataFrame([])
    provider = AkshareNewsProvider(fetchers={
        "eastmoney": blocked,
        "sina": lambda: pd.DataFrame([{"标题": "测试资讯", "内容": "内容", "时间": now.isoformat()}]),
    }, timeout_seconds=0.02)
    handler = ResilientLatestNewsHandler(provider)
    try:
        first = await handler.handle(sources=("eastmoney", "sina"), lookback=timedelta(hours=24))
        assert first[0].publisher == "sina"
        with pytest.raises(RuntimeError, match="timed out"):
            await provider.fetch_latest(sources=("eastmoney",), lookback=timedelta(hours=24))
        assert calls == ["eastmoney"]
    finally:
        release.set()
        await asyncio.gather(*provider._pending.values(), return_exceptions=True)


@pytest.mark.asyncio
async def test_concurrent_requests_share_cache_and_expired_articles_are_not_reused():
    now = datetime(2026, 11, 9, 2, 30, tzinfo=UTC)
    article = NewsArticle("标题", "正文", "sina", now - timedelta(minutes=59))
    provider = AsyncMock()
    provider.fetch_latest.return_value = [article]
    handler = ResilientLatestNewsHandler(provider, clock=lambda: now)
    await asyncio.gather(*(handler.handle(sources=("sina",), lookback=timedelta(hours=1)) for _ in range(5)))
    assert provider.fetch_latest.await_count == 1
    now += timedelta(minutes=2)
    provider.fetch_latest.side_effect = RuntimeError("offline")
    with pytest.raises(NewsCollectionUnavailableError):
        await handler.handle(sources=("sina",), lookback=timedelta(hours=1))
