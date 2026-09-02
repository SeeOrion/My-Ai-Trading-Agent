"""News collection and analysis use cases."""

from __future__ import annotations

from collections.abc import Iterable
from datetime import timedelta
from typing import Protocol

from ai_trading_agent.domain.news import (
    LLMNewsAssessment,
    NewsAnalysisResult,
    NewsArticle,
    deduplicate_articles,
)
from ai_trading_agent.domain.research import analyze_financial_sentiment


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
