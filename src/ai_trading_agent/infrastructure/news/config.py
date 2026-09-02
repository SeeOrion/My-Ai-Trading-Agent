"""Environment-backed configuration for News Intelligence adapters."""

from __future__ import annotations

import os
from dataclasses import dataclass


class NewsConfigurationError(RuntimeError):
    """Raised when an enabled news adapter lacks mandatory configuration."""


@dataclass(frozen=True, slots=True)
class ArticleFetcherSettings:
    allowed_hosts: frozenset[str]
    timeout_seconds: float = 15.0
    max_content_bytes: int = 1_000_000

    @classmethod
    def from_environment(cls) -> ArticleFetcherSettings:
        hosts = frozenset(
            host.strip().lower()
            for host in os.environ.get("NEWS_ALLOWED_HOSTS", "").split(",")
            if host.strip()
        )
        if not hosts:
            raise NewsConfigurationError("NEWS_ALLOWED_HOSTS is required for article fetching")
        return cls(allowed_hosts=hosts)


@dataclass(frozen=True, slots=True)
class OpenAICompatibleLLMSettings:
    api_key: str
    model: str
    base_url: str = "https://api.openai.com/v1"
    timeout_seconds: float = 30.0

    @classmethod
    def from_environment(cls) -> OpenAICompatibleLLMSettings:
        api_key = os.environ.get("LLM_API_KEY", "").strip()
        model = os.environ.get("LLM_MODEL", "").strip()
        base_url = os.environ.get("LLM_BASE_URL", "https://api.openai.com/v1").rstrip("/")
        if not api_key:
            raise NewsConfigurationError("LLM_API_KEY is required for model-based news analysis")
        if not model:
            raise NewsConfigurationError("LLM_MODEL is required for model-based news analysis")
        if not base_url.startswith(("https://", "http://")):
            raise NewsConfigurationError("LLM_BASE_URL must be an HTTP(S) URL")
        return cls(api_key=api_key, model=model, base_url=base_url)
