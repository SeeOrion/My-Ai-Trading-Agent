from datetime import UTC, datetime, timedelta

import pytest

from ai_trading_agent.application.news import (
    AnalyzeNewsArticleHandler,
    CollectLatestNewsHandler,
    ResilientLatestNewsHandler,
)
from ai_trading_agent.domain.aggregate.news import LLMNewsAssessment, NewsArticle


class FakeNewsProvider:
    async def fetch_latest(
        self, *, sources: tuple[str, ...], lookback: timedelta
    ) -> list[NewsArticle]:
        return [
            NewsArticle("Growth", "Profit growth", sources[0], datetime(2026, 9, 2, tzinfo=UTC))
        ]


class FakeAnalyzer:
    async def analyze(self, article: NewsArticle) -> LLMNewsAssessment:
        return LLMNewsAssessment("summary", "positive", 0.8, ("growth",), (), "fake")


class OrderedNewsProvider:
    def __init__(self, outcomes: dict[str, list[NewsArticle] | Exception]) -> None:
        self.outcomes = outcomes
        self.calls: list[str] = []

    async def fetch_latest(
        self, *, sources: tuple[str, ...], lookback: timedelta
    ) -> list[NewsArticle]:
        source = sources[0]
        self.calls.append(source)
        outcome = self.outcomes[source]
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


class MutableClock:
    def __init__(self, value: datetime) -> None:
        self.value = value

    def now(self) -> datetime:
        return self.value


def _article(source: str) -> NewsArticle:
    return NewsArticle("Market update", "Profit growth", source, datetime(2026, 9, 2, tzinfo=UTC))


@pytest.mark.asyncio
async def test_collect_latest_news_delegates_to_provider() -> None:
    articles = await CollectLatestNewsHandler(FakeNewsProvider()).handle(
        sources=("sina",), lookback=timedelta(hours=1)
    )

    assert articles[0].publisher == "sina"


@pytest.mark.asyncio
async def test_resilient_news_uses_sina_when_eastmoney_fails() -> None:
    provider = OrderedNewsProvider(
        {"eastmoney": RuntimeError("upstream down"), "sina": [_article("sina")]}
    )
    handler = ResilientLatestNewsHandler(provider)

    articles = await handler.handle(
        sources=("eastmoney", "sina"), lookback=timedelta(hours=24)
    )

    assert provider.calls == ["eastmoney", "sina"]
    assert articles[0].publisher == "sina"


@pytest.mark.asyncio
async def test_resilient_news_caches_and_uses_stale_cache_on_source_errors() -> None:
    clock = MutableClock(datetime(2026, 9, 2, tzinfo=UTC))
    provider = OrderedNewsProvider(
        {"eastmoney": [_article("eastmoney")], "sina": [_article("sina")]}
    )
    handler = ResilientLatestNewsHandler(
        provider,
        cache_ttl=timedelta(minutes=2),
        stale_if_error=timedelta(minutes=10),
        clock=clock.now,
    )

    first = await handler.handle(sources=("eastmoney", "sina"), lookback=timedelta(hours=24))
    cached = await handler.handle(sources=("eastmoney", "sina"), lookback=timedelta(hours=24))
    clock.value += timedelta(minutes=3)
    provider.outcomes = {"eastmoney": RuntimeError("down"), "sina": RuntimeError("down")}
    stale = await handler.handle(sources=("eastmoney", "sina"), lookback=timedelta(hours=24))

    assert [batch[0].publisher for batch in (first, cached, stale)] == [
        "eastmoney",
        "eastmoney",
        "eastmoney",
    ]
    assert provider.calls == ["eastmoney", "eastmoney", "sina"]


@pytest.mark.asyncio
async def test_news_analysis_combines_baseline_and_model_assessment() -> None:
    article = NewsArticle("Upgrade", "Profit growth", "source", datetime(2026, 9, 2, tzinfo=UTC))

    result = await AnalyzeNewsArticleHandler(FakeAnalyzer()).handle(article)

    assert result.lexicon_sentiment.label == "positive"
    assert result.llm_assessment.model == "fake"
