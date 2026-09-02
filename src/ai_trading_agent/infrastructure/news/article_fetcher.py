"""Allowlisted, bounded HTML article retrieval and text extraction."""

from __future__ import annotations

from urllib.parse import urlsplit

import httpx
from bs4 import BeautifulSoup

from ai_trading_agent.infrastructure.news.config import ArticleFetcherSettings


class ArticleFetchError(RuntimeError):
    """Raised when an article URL violates the reader policy or cannot be read."""


class AllowlistedArticleContentFetcher:
    """Fetch articles only from configured public publisher hosts.

    URL allowlisting and no redirects make the reader suitable for passing
    content onward to an LLM without giving it arbitrary network reachability.
    """

    def __init__(
        self,
        settings: ArticleFetcherSettings,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._settings = settings
        self._transport = transport

    async def fetch(self, url: str) -> str:
        self._validate_url(url)
        timeout = httpx.Timeout(self._settings.timeout_seconds)
        async with httpx.AsyncClient(
            timeout=timeout,
            follow_redirects=False,
            transport=self._transport,
        ) as client:
            response = await client.get(url, headers={"User-Agent": "My-Ai-Trading-Agent/0.1"})
            response.raise_for_status()
            content_type = response.headers.get("content-type", "").lower()
            if "html" not in content_type:
                raise ArticleFetchError("article response must be HTML")
            if len(response.content) > self._settings.max_content_bytes:
                raise ArticleFetchError("article response exceeds the configured size limit")
        text = _extract_readable_text(response.text)
        if not text:
            raise ArticleFetchError("article contains no readable text")
        return text

    def _validate_url(self, url: str) -> None:
        parsed = urlsplit(url)
        host = (parsed.hostname or "").lower()
        if parsed.scheme not in {"https", "http"}:
            raise ArticleFetchError("article URL must use HTTP(S)")
        if parsed.username or parsed.password or not host:
            raise ArticleFetchError("article URL must not contain credentials")
        if host not in self._settings.allowed_hosts:
            raise ArticleFetchError(f"article host is not allowlisted: {host}")


def _extract_readable_text(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    for element in soup(["script", "style", "nav", "header", "footer", "noscript"]):
        element.decompose()
    root = soup.find("article") or soup.body or soup
    return " ".join(root.get_text(" ", strip=True).split())[:20_000]
