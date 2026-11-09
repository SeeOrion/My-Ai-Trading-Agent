"""Bounded reader of Eastmoney's public website search feed, without credentials."""

import asyncio
import json
import re
from datetime import UTC, datetime, timedelta

import httpx
from bs4 import BeautifulSoup

from ai_trading_agent.domain.aggregate.news import NewsArticle, deduplicate_articles
from ai_trading_agent.infrastructure.rpc.akshare_news import _published_at


def _clean(value):
    soup = BeautifulSoup(str(value or ""), "html.parser")
    for tag in soup.find_all(["em", "b", "strong", "span"]):
        tag.unwrap()
    for tag in soup.find_all(["script", "style"]):
        tag.decompose()
    return soup.get_text("", strip=True)


class PublicNewsSearch:
    def __init__(self, *, transport=None):
        self._transport = transport
        self._cache = {}
        self._lock = asyncio.Lock()

    async def search(self, terms: tuple[str, ...]) -> list[NewsArticle]:
        # One bounded request per term, at most three terms; shared across accounts.
        async with self._lock:
            articles = []
            async with httpx.AsyncClient(timeout=3, transport=self._transport, follow_redirects=False) as client:
                for term in tuple(dict.fromkeys(t.strip() for t in terms if t.strip()))[:3]:
                    now = datetime.now(UTC)
                    cached = self._cache.get(term)
                    if cached and now < cached[0]:
                        articles.extend(cached[1])
                        continue
                    try:
                        rows = await self._fetch(client, term)
                    except (httpx.HTTPError, ValueError, KeyError, TypeError):
                        rows = cached[1] if cached else []
                    if len(self._cache) >= 512:
                        self._cache.pop(next(iter(self._cache)))
                    self._cache[term] = (now + timedelta(minutes=10), rows)
                    articles.extend(rows)
            cutoff = datetime.now(UTC) - timedelta(hours=24)
            return deduplicate_articles([a for a in articles if cutoff <= a.published_at <= datetime.now(UTC) + timedelta(minutes=5)])

    async def _fetch(self, client, term):
        params = {"uid": "", "keyword": term[:80], "type": ["cmsArticleWebOld"], "client": "web",
                  "clientType": "web", "clientVersion": "curr",
                  "param": {"cmsArticleWebOld": {"searchScope": "default", "sort": "latest",
                            "pageIndex": 1, "pageSize": 30, "preTag": "", "postTag": ""}}}
        async with client.stream("GET", "https://search-api-web.eastmoney.com/search/jsonp",
                                 params={"cb": "newsCallback", "param": json.dumps(params, ensure_ascii=False)},
                                 headers={"User-Agent": "My-Ai-Trading-Agent/0.1", "Referer": "https://so.eastmoney.com/"}) as response:
            response.raise_for_status()
            raw = bytearray()
            async for chunk in response.aiter_bytes():
                raw.extend(chunk)
                if len(raw) > 1_000_000:
                    raise ValueError("public news response too large")
        body = raw.decode("utf-8").strip()
        if body.startswith("newsCallback("):
            body = body[len("newsCallback("):].rstrip("; ").removesuffix(")")
        rows = json.loads(body)["result"]["cmsArticleWebOld"]
        articles = []
        for row in rows[:30]:
            at = _published_at({"发布时间": row.get("date")})
            title = _clean(row.get("title"))
            content = _clean(row.get("content") or title)
            code = str(row.get("code") or "")
            if at and title and content:
                articles.append(NewsArticle(title, content[:6000], str(row.get("mediaName") or "东方财富公开检索"), at,
                    f"https://finance.eastmoney.com/a/{code}.html" if re.fullmatch(r"\d+", code) else None))
        return articles
