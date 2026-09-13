"""Use case for requesting a natural-language, source-grounded market answer."""

from __future__ import annotations

from typing import Protocol


class MarketQuestionAdvisor(Protocol):
    async def answer(self, *, question: str, context: str) -> str: ...


class AnswerMarketQuestionHandler:
    """Keep the model dependency behind an application-level contract."""

    def __init__(self, advisor: MarketQuestionAdvisor) -> None:
        self._advisor = advisor

    async def handle(self, *, question: str, context: str) -> str:
        if not question.strip():
            raise ValueError("market question must not be empty")
        if not context.strip():
            raise ValueError("market question context must not be empty")
        return await self._advisor.answer(question=question, context=context)
