from datetime import UTC, datetime, timedelta

from ai_trading_agent.domain.aggregate.news import NewsArticle, deduplicate_articles


def test_deduplication_keeps_newest_publisher_title_pair() -> None:
    now = datetime(2026, 9, 2, 12, tzinfo=UTC)
    older = NewsArticle("Earnings growth", "old", "source", now - timedelta(minutes=2))
    newer = NewsArticle(" earnings   growth ", "new", "source", now)

    articles = deduplicate_articles([older, newer])

    assert articles == [newer]
