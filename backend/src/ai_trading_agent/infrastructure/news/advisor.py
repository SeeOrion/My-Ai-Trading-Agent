"""OpenAI-compatible, source-grounded research conversation adapter."""

from __future__ import annotations

import httpx

from ai_trading_agent.infrastructure.news.config import OpenAICompatibleLLMSettings


class LLMResearchAdvisorError(RuntimeError):
    """Raised when the configured model cannot answer a research question."""


class OpenAICompatibleResearchAdvisor:
    def __init__(self, settings: OpenAICompatibleLLMSettings) -> None:
        self._settings = settings

    async def answer(self, *, question: str, context: str) -> str:
        payload = {
            "model": self._settings.model,
            "temperature": 0.2,
            "messages": [
                {"role": "system", "content": _SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": f"Research context:\n{context}\n\nUser question:\n{question}",
                },
            ],
        }
        headers = {"Authorization": f"Bearer {self._settings.api_key}"}
        try:
            async with httpx.AsyncClient(timeout=self._settings.timeout_seconds) as client:
                response = await client.post(
                    f"{self._settings.base_url}/chat/completions", json=payload, headers=headers
                )
                response.raise_for_status()
                content = response.json()["choices"][0]["message"]["content"]
        except (httpx.HTTPError, KeyError, IndexError, TypeError, ValueError) as error:
            raise LLMResearchAdvisorError(f"model request failed: {error}") from error
        answer = str(content).strip()
        if not answer:
            raise LLMResearchAdvisorError("model returned an empty answer")
        return answer


_SYSTEM_PROMPT = """You are a careful financial research assistant.
Use only the supplied context and clearly distinguish facts, unavailable data, and inference.
Respect the user's strategy as a research preference, not an instruction to trade. Do not promise
returns, give personalised execution instructions, or invent market/news data. Answer in Chinese
unless the user asks otherwise. End with a concise risk reminder."""
