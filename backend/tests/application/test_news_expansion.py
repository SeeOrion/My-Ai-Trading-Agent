import asyncio
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock

import httpx
import pytest

from ai_trading_agent.application.news import ResilientLatestNewsHandler
from ai_trading_agent.application.news_brief import CachedNewsBriefs
from ai_trading_agent.domain.aggregate.news import LLMNewsAssessment, NewsArticle
from ai_trading_agent.infrastructure.rpc.public_news_search import PublicNewsSearch


@pytest.mark.asyncio
async def test_aggregate_collects_both_sources_and_survives_one_failure():
    article = lambda name: NewsArticle(name, name, name, datetime.now(UTC))
    provider = AsyncMock()
    async def fetch(*, sources, lookback):
        if sources == ("broken",):
            raise RuntimeError("offline")
        return [article(sources[0])]
    provider.fetch_latest.side_effect = fetch
    handler = ResilientLatestNewsHandler(provider, aggregate_sources=True)
    result = await handler.handle(sources=["eastmoney", "broken", "sina"], lookback=timedelta(hours=24))
    assert {a.title for a in result} == {"eastmoney", "sina"}
    await handler.handle(sources=["eastmoney", "broken", "sina"], lookback=timedelta(hours=24))
    assert provider.fetch_latest.call_count == 3


@pytest.mark.asyncio
async def test_search_strips_html_caches_and_excludes_stale_news():
    import json
    calls = []
    def respond(request):
        calls.append(request)
        rows = [{"title": "<em>中粮</em>增长", "content": "盈利增长", "date": datetime.now(UTC).isoformat(), "code": "123", "mediaName": "公开来源"},
                {"title": "旧闻", "content": "旧闻", "date": "2020-01-01 09:00:00"}]
        return httpx.Response(200, text="newsCallback(" + json.dumps({"result": {"cmsArticleWebOld": rows}}) + ");")
    search = PublicNewsSearch(transport=httpx.MockTransport(respond))
    result = await search.search(("中粮",))
    assert len(result) == 1 and result[0].title == "中粮增长"
    assert result[0].url == "https://finance.eastmoney.com/a/123.html"
    await search.search(("中粮",))
    assert len(calls) == 1


@pytest.mark.asyncio
async def test_brief_ignores_timestamps_and_order_singleflight_and_budget():
    cache = CachedNewsBriefs()
    analyzer = AsyncMock()
    analyzer.analyze.return_value = LLMNewsAssessment("盈利改善", "positive", .8, (), (), "model")
    args = dict(analyzer=analyzer, model="model", subject="600737", layer="个股", hourly_limit=1)
    first = [{"title": "A", "excerpt": "盈利增长", "published_at": "old"}, {"title": "B", "excerpt": "稳健"}]
    results = await asyncio.gather(cache.interpret(**args, evidence=first), cache.interpret(**args, evidence=list(reversed(first))))
    assert analyzer.analyze.call_count == 1
    assert results[1]["cached"]
    first[0]["published_at"] = "new"
    assert (await cache.interpret(**args, evidence=first))["cached"]
    assert (await cache.interpret(**args, evidence=[{"title": "新重大事件"}]))["status"] == "budget_limited"


@pytest.mark.asyncio
async def test_brief_failure_backoff_and_no_evidence_do_not_retry_model():
    cache = CachedNewsBriefs()
    analyzer = AsyncMock()
    analyzer.analyze.side_effect = RuntimeError("offline")
    args = dict(analyzer=analyzer, model="m", subject="s", layer="个股")
    assert (await cache.interpret(**args, evidence=[]))["status"] == "no_evidence"
    for _ in range(2):
        assert (await cache.interpret(**args, evidence=[{"title": "新消息"}]))["status"] == "unavailable"
    assert analyzer.analyze.call_count == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("eligible,confidence,expected", [(False, .9, "0.1"), (True, .5, "0.1"), (True, .9, "-0.5")])
async def test_model_factor_requires_direct_evidence_and_confidence(monkeypatch, eligible, confidence, expected):
    from decimal import Decimal
    from ai_trading_agent.interfaces.facade import news_research as service
    from ai_trading_agent.domain.service.news_relevance import NewsSubject
    from ai_trading_agent.infrastructure.config.news import OpenAICompatibleLLMSettings
    monkeypatch.setattr(service.OpenAICompatibleLLMSettings, "from_environment", lambda: OpenAICompatibleLLMSettings("test", "test"))
    monkeypatch.setattr(service._briefs, "interpret", AsyncMock(return_value={"status": "completed", "summary": "风险增加", "confidence": confidence, "sentiment": "negative"}))
    result = {"instrument": {"evidence": []}, "score": Decimal("0.1"), "factor_eligible": eligible, "summary": "原始证据", "limitations": []}
    await service._interpret_news(result, NewsSubject("600737.SH"))
    assert result["score"] == Decimal(expected)
