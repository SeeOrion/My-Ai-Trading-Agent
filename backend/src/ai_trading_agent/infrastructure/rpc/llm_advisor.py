"""OpenAI-compatible, source-grounded research conversation adapter."""

from __future__ import annotations

import asyncio

import httpx

from ai_trading_agent.infrastructure.config.news import OpenAICompatibleLLMSettings
from ai_trading_agent.infrastructure.rpc.llm_usage import record_usage


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
        body = {}
        try:
            async with httpx.AsyncClient(timeout=self._settings.timeout_seconds) as client:
                response = await client.post(
                    f"{self._settings.base_url}/chat/completions", json=payload, headers=headers
                )
                response.raise_for_status()
                body = response.json()
                content = body["choices"][0]["message"]["content"]
                if not isinstance(content, str) or not content.strip():
                    raise ValueError("model returned an empty answer")
        except asyncio.CancelledError:
            await record_usage(model=self._settings.model, status="failed", body=body, reason="请求取消或超时，用量可能未知")
            raise
        except (httpx.HTTPError, KeyError, IndexError, TypeError, ValueError) as error:
            await record_usage(model=self._settings.model, status="failed", body=body)
            raise LLMResearchAdvisorError(f"model request failed: {error}") from error
        await record_usage(model=self._settings.model, status="success", body=body)
        answer = str(content).strip()
        if not answer:
            raise LLMResearchAdvisorError("model returned an empty answer")
        return answer


_SYSTEM_PROMPT = """You are a careful financial research assistant.
Use only the supplied context and clearly distinguish facts, unavailable data, and inference.
Respect the user's strategy as a research preference, not an instruction to trade. Do not promise
returns, give personalised execution instructions, or invent market/news data. If the context
contains "Deterministic personal-discipline status", that status was calculated by a rule engine:
do not alter, override, or create another status. Explain its market and research evidence only,
and explicitly identify missing or stale data. Never imply that an order was placed or should be
placed automatically. Answer in Chinese unless the user asks otherwise. Use plain text rather
than Markdown markers, unless the user explicitly asks for a Markdown document. End with a
concise risk reminder."""
