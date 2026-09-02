from datetime import UTC, datetime

import httpx
import pytest

from ai_trading_agent.domain.news import NewsArticle
from ai_trading_agent.infrastructure.news.article_fetcher import (
    AllowlistedArticleContentFetcher,
    ArticleFetchError,
)
from ai_trading_agent.infrastructure.news.config import (
    ArticleFetcherSettings,
    OpenAICompatibleLLMSettings,
)
from ai_trading_agent.infrastructure.news.llm import OpenAICompatibleNewsAnalyzer


@pytest.mark.asyncio
async def test_article_fetcher_extracts_article_content_from_allowed_host() -> None:
    transport = httpx.MockTransport(
        lambda request: httpx.Response(
            200,
            headers={"content-type": "text/html"},
            text=(
                "<html><body><nav>menu</nav><article><h1>Title</h1>"
                "<p>News body</p></article></body></html>"
            ),
        )
    )
    fetcher = AllowlistedArticleContentFetcher(
        ArticleFetcherSettings(frozenset({"news.example.com"})), transport=transport
    )

    text = await fetcher.fetch("https://news.example.com/article")

    assert text == "Title News body"


@pytest.mark.asyncio
async def test_article_fetcher_rejects_unapproved_host() -> None:
    settings = ArticleFetcherSettings(frozenset({"news.example.com"}))
    fetcher = AllowlistedArticleContentFetcher(settings)

    with pytest.raises(ArticleFetchError, match="not allowlisted"):
        await fetcher.fetch("https://internal.example/article")


@pytest.mark.asyncio
async def test_openai_compatible_analyzer_requires_structured_response() -> None:
    transport = httpx.MockTransport(
        lambda request: httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": '{"summary":"profit grew","sentiment":"positive",'
                            '"confidence":0.8,"material_events":["earnings"],"risks":[]}'
                        }
                    }
                ]
            },
        )
    )
    analyzer = OpenAICompatibleNewsAnalyzer(
        OpenAICompatibleLLMSettings("secret", "test-model", "https://llm.example/v1"),
        transport=transport,
    )
    article = NewsArticle("Title", "Profit grew", "source", datetime(2026, 9, 2, tzinfo=UTC))

    assessment = await analyzer.analyze(article)

    assert assessment.summary == "profit grew"
    assert assessment.material_events == ("earnings",)
