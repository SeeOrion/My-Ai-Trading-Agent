"""OpenAI-compatible, source-grounded news-analysis adapter."""

from __future__ import annotations

import json

import httpx

from ai_trading_agent.domain.aggregate.news import LLMNewsAssessment, NewsArticle
from ai_trading_agent.infrastructure.config.news import OpenAICompatibleLLMSettings


class LLMNewsAnalysisError(RuntimeError):
    """Raised when a model endpoint fails or does not return the required JSON."""


class OpenAICompatibleNewsAnalyzer:
    """Analyze supplied source text through a configured Chat Completions endpoint."""

    def __init__(
        self,
        settings: OpenAICompatibleLLMSettings,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._settings = settings
        self._transport = transport

    async def analyze(self, article: NewsArticle) -> LLMNewsAssessment:
        payload = {
            "model": self._settings.model,
            "temperature": 0,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": _SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": (
                        f"Publisher: {article.publisher}\n"
                        f"Published at: {article.published_at.isoformat()}\n"
                        f"Title: {article.title}\n\nArticle text:\n{article.content[:20_000]}"
                    ),
                },
            ],
        }
        headers = {"Authorization": f"Bearer {self._settings.api_key}"}
        try:
            async with httpx.AsyncClient(
                timeout=httpx.Timeout(self._settings.timeout_seconds), transport=self._transport
            ) as client:
                response = await client.post(
                    f"{self._settings.base_url}/chat/completions", json=payload, headers=headers
                )
                response.raise_for_status()
        except httpx.HTTPError as error:
            raise LLMNewsAnalysisError(f"model request failed: {error}") from error
        try:
            content = response.json()["choices"][0]["message"]["content"]
            parsed = json.loads(_strip_code_fence(str(content)))
            return LLMNewsAssessment(
                summary=str(parsed["summary"]),
                sentiment=str(parsed["sentiment"]).lower(),
                confidence=float(parsed["confidence"]),
                material_events=tuple(str(value) for value in parsed.get("material_events", [])),
                risks=tuple(str(value) for value in parsed.get("risks", [])),
                model=self._settings.model,
            )
        except (KeyError, IndexError, TypeError, ValueError, json.JSONDecodeError) as error:
            raise LLMNewsAnalysisError(
                "model response did not match the required JSON contract"
            ) from error


_SYSTEM_PROMPT = """You are a financial-news analyst. Use only the supplied article text.
Do not invent facts, prices, or investment recommendations. Return a JSON object with exactly
these fields: summary (string), sentiment (positive|neutral|negative), confidence (number 0..1),
material_events (array of strings), risks (array of strings). Mark ambiguity as a risk."""


def _strip_code_fence(content: str) -> str:
    stripped = content.strip()
    if stripped.startswith("```") and stripped.endswith("```"):
        return stripped.split("\n", maxsplit=1)[1].rsplit("\n", maxsplit=1)[0]
    return stripped
