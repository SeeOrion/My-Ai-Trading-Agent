"""Bounded, content-addressed news interpretation; no orders or provider dependencies."""

import asyncio
import hashlib
import json
import re
from dataclasses import asdict
from datetime import UTC, datetime, timedelta

from ai_trading_agent.application.news import NewsAnalyzer
from ai_trading_agent.domain.aggregate.news import NewsArticle


class CachedNewsBriefs:
    """Process-local cache shared by accounts; restart clears cache and hourly budget."""

    def __init__(self):
        self._cache = {}
        self._lock = asyncio.Lock()
        self._calls = []

    async def interpret(self, *, analyzer: NewsAnalyzer, model: str, subject: str,
                        layer: str, evidence: list[dict], hourly_limit: int = 12) -> dict:
        # Only normalized evidence enters both digest and prompt. No query times,
        # publication timestamps, URLs or provider request identifiers in the key.
        items = sorted({json.dumps({"title": re.sub(r"\s+", " ", str(e.get("title", ""))).strip(),
                                   "excerpt": re.sub(r"\s+", " ", str(e.get("excerpt", ""))).strip()[:600]},
                                  ensure_ascii=False, sort_keys=True) for e in evidence[:5]})
        if not items:
            return {"status": "no_evidence"}
        content = "\n".join(items)
        key = hashlib.sha256(f"v1|{model}|{subject}|{layer}|{content}".encode()).hexdigest()
        async with self._lock:
            now = datetime.now(UTC)
            cached = self._cache.get(key)
            if cached and now < cached[0]:
                return {**cached[1], "cached": True}
            self._calls = [t for t in self._calls if now - t < timedelta(hours=1)]
            if len(self._calls) >= hourly_limit:
                return {"status": "budget_limited"}
            self._calls.append(now)
            article = NewsArticle(f"{subject}：{layer}相关新闻", content, "公开资讯筛选样本", now)
            try:
                assessment = await analyzer.analyze(article)
                result = {"status": "completed", **asdict(assessment), "cached": False,
                          "generated_at": now.isoformat()}
                ttl = timedelta(hours=24)
            except Exception:
                result = {"status": "unavailable", "cached": False}
                ttl = timedelta(minutes=10)
            if len(self._cache) >= 512:
                self._cache.pop(next(iter(self._cache)))
            self._cache[key] = (now + ttl, result)
            return result
