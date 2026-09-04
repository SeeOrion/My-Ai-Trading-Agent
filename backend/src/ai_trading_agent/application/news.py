"""News collection and analysis use cases."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Protocol

from ai_trading_agent.domain.aggregate.news import (
    LLMNewsAssessment,
    NewsAnalysisResult,
    NewsArticle,
    deduplicate_articles,
)
from ai_trading_agent.domain.aggregate.research import analyze_financial_sentiment


class NewsProvider(Protocol):
    async def fetch_latest(
        self, *, sources: Iterable[str], lookback: timedelta
    ) -> list[NewsArticle]:
        """Fetch source-attributed items published within the requested window."""


class ArticleContentFetcher(Protocol):
    async def fetch(self, url: str) -> str:
        """Fetch and extract readable article content from an approved URL."""


class NewsAnalyzer(Protocol):
    async def analyze(self, article: NewsArticle) -> LLMNewsAssessment:
        """Return structured analysis grounded solely in the supplied article."""


class NewsCollectionUnavailableError(RuntimeError):
    """Raised only after every requested source and usable cache has failed."""


@dataclass(frozen=True, slots=True)
class _CachedNews:
    articles: tuple[NewsArticle, ...]
    collected_at: datetime


class ResilientLatestNewsHandler:
    """Collect ordered public sources with a short cache and stale fallback.

    Sources are queried one at a time. This prevents an upstream failure at the
    preferred source from suppressing the remaining source, and keeps repeated
    dashboard/chat requests from needlessly hitting public endpoints.
    """

    def __init__(
        self,
        provider: NewsProvider,
        *,
        cache_ttl: timedelta = timedelta(minutes=2),
        stale_if_error: timedelta = timedelta(minutes=10),
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        if cache_ttl <= timedelta(0):
            raise ValueError("cache_ttl must be positive")
        if stale_if_error < cache_ttl:
            raise ValueError("stale_if_error must be at least cache_ttl")
        self._provider = provider
        self._cache_ttl = cache_ttl
        self._stale_if_error = stale_if_error
        self._clock = clock or (lambda: datetime.now(UTC))
        self._cache: dict[tuple[tuple[str, ...], timedelta], _CachedNews] = {}

    async def handle(
        self, *, sources: Iterable[str], lookback: timedelta
    ) -> list[NewsArticle]:
        if lookback <= timedelta(0):
            raise ValueError("lookback must be positive")
        normalized_sources = _normalize_sources(sources)
        key = (normalized_sources, lookback)
        now = self._now()
        cached = self._cache.get(key)
        if cached is not None and now - cached.collected_at <= self._cache_ttl:
            return list(cached.articles)

        errors: list[str] = []
        for source in normalized_sources:
            try:
                articles = deduplicate_articles(
                    await self._provider.fetch_latest(sources=(source,), lookback=lookback)
                )
            except Exception as error:
                errors.append(f"{source}: {error}")
                continue
            if not articles:
                errors.append(f"{source}: no recent articles")
                continue
            self._cache[key] = _CachedNews(tuple(articles), now)
            return articles

        if cached is not None and now - cached.collected_at <= self._stale_if_error:
            return list(cached.articles)
        detail = "; ".join(errors) or "no public news source configured"
        raise NewsCollectionUnavailableError(detail)

    def _now(self) -> datetime:
        now = self._clock()
        if now.tzinfo is None:
            raise ValueError("clock must return a timezone-aware datetime")
        return now.astimezone(UTC)


def _normalize_sources(sources: Iterable[str]) -> tuple[str, ...]:
    normalized = tuple(
        dict.fromkeys(source.strip().lower() for source in sources if source.strip())
    )
    if not normalized:
        raise ValueError("at least one news source is required")
    return normalized


class CollectLatestNewsHandler:
    def __init__(self, provider: NewsProvider) -> None:
        self._provider = provider

    async def handle(self, *, sources: Iterable[str], lookback: timedelta) -> list[NewsArticle]:
        if lookback <= timedelta(0):
            raise ValueError("lookback must be positive")
        return deduplicate_articles(
            await self._provider.fetch_latest(sources=tuple(sources), lookback=lookback)
        )


class AnalyzeNewsArticleHandler:
    def __init__(
        self, analyzer: NewsAnalyzer, content_fetcher: ArticleContentFetcher | None = None
    ) -> None:
        self._analyzer = analyzer
        self._content_fetcher = content_fetcher

    async def handle(
        self, article: NewsArticle, *, fetch_full_content: bool = False
    ) -> NewsAnalysisResult:
        enriched_article = article
        if fetch_full_content:
            if self._content_fetcher is None:
                raise ValueError("a content fetcher is required to fetch full article content")
            if article.url is None:
                raise ValueError("article has no URL for full-content retrieval")
            enriched_article = article.with_content(await self._content_fetcher.fetch(article.url))
        lexicon_sentiment = analyze_financial_sentiment(
            f"{enriched_article.title}\n{enriched_article.content}"
        )
        return NewsAnalysisResult(
            article=enriched_article,
            lexicon_sentiment=lexicon_sentiment,
            llm_assessment=await self._analyzer.analyze(enriched_article),
        )
