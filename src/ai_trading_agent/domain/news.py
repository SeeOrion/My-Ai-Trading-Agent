"""News Intelligence bounded context: source facts, deduplication, and analyses."""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import UTC, datetime

from ai_trading_agent.domain.research import SentimentAssessment


@dataclass(frozen=True, slots=True)
class NewsArticle:
    """A source-attributed news item; content may be a flash or full article."""

    title: str
    content: str
    publisher: str
    published_at: datetime
    url: str | None = None

    def __post_init__(self) -> None:
        if not self.title.strip():
            raise ValueError("title must not be empty")
        if not self.content.strip():
            raise ValueError("content must not be empty")
        if not self.publisher.strip():
            raise ValueError("publisher must not be empty")
        if self.published_at.tzinfo is None:
            raise ValueError("published_at must be timezone-aware")
        object.__setattr__(self, "title", self.title.strip())
        object.__setattr__(self, "content", self.content.strip())
        object.__setattr__(self, "publisher", self.publisher.strip())
        object.__setattr__(self, "published_at", self.published_at.astimezone(UTC))
        if self.url is not None:
            object.__setattr__(self, "url", self.url.strip() or None)

    def with_content(self, content: str) -> NewsArticle:
        return replace(self, content=content)


@dataclass(frozen=True, slots=True)
class LLMNewsAssessment:
    """Structured model output, always paired with the source article."""

    summary: str
    sentiment: str
    confidence: float
    material_events: tuple[str, ...]
    risks: tuple[str, ...]
    model: str

    def __post_init__(self) -> None:
        if not self.summary.strip():
            raise ValueError("summary must not be empty")
        if self.sentiment not in {"positive", "neutral", "negative"}:
            raise ValueError("sentiment must be positive, neutral, or negative")
        if not 0 <= self.confidence <= 1:
            raise ValueError("confidence must be between 0 and 1")
        if not self.model.strip():
            raise ValueError("model must not be empty")


@dataclass(frozen=True, slots=True)
class NewsAnalysisResult:
    article: NewsArticle
    lexicon_sentiment: SentimentAssessment
    llm_assessment: LLMNewsAssessment


def deduplicate_articles(articles: list[NewsArticle]) -> list[NewsArticle]:
    """Retain the newest article for each publisher/title or URL identity."""
    newest_first = sorted(articles, key=lambda article: article.published_at, reverse=True)
    seen: set[str] = set()
    unique: list[NewsArticle] = []
    for article in newest_first:
        identity = article.url or f"{article.publisher.lower()}::{_normalize_title(article.title)}"
        if identity not in seen:
            seen.add(identity)
            unique.append(article)
    return unique


def _normalize_title(title: str) -> str:
    return " ".join(title.lower().split())
