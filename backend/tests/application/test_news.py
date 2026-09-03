from datetime import UTC, datetime, timedelta

import pytest

from ai_trading_agent.application.news import AnalyzeNewsArticleHandler, CollectLatestNewsHandler
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


@pytest.mark.asyncio
async def test_collect_latest_news_delegates_to_provider() -> None:
    articles = await CollectLatestNewsHandler(FakeNewsProvider()).handle(
        sources=("sina",), lookback=timedelta(hours=1)
    )

    assert articles[0].publisher == "sina"


@pytest.mark.asyncio
async def test_news_analysis_combines_baseline_and_model_assessment() -> None:
    article = NewsArticle("Upgrade", "Profit growth", "source", datetime(2026, 9, 2, tzinfo=UTC))

    result = await AnalyzeNewsArticleHandler(FakeAnalyzer()).handle(article)

    assert result.lexicon_sentiment.label == "positive"
    assert result.llm_assessment.model == "fake"
