"""Bounded adaptive research loop. Model and tools are injected ports, never orders."""

import asyncio
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Awaitable, Callable, Protocol
from ai_trading_agent.domain.service.agent_evidence import InsufficientEvidence


class ResearchModel(Protocol):
    async def step(self, context: dict, history: list[dict], *, token_budget: int) -> dict:
        """Return tool(name, arguments) or finish(report), plus total_tokens consumed."""


@dataclass(frozen=True)
class AgentLimits:
    rounds: int = 6
    tokens: int = 6000
    timeout_seconds: float = 45
    repeated_queries: int = 1

    def __post_init__(self):
        if min(self.rounds, self.tokens, self.timeout_seconds, self.repeated_queries) <= 0:
            raise ValueError("agent limits must be positive")


@dataclass
class AgentResult:
    status: str
    report: dict | None = None
    trace: list[dict] = field(default_factory=list)
    tokens: int = 0
    steps: list[dict] = field(default_factory=list)


class ResearchAgent:
    def __init__(
        self,
        model: ResearchModel,
        tools: dict[str, Callable[[dict], Awaitable[dict]]],
        *,
        validate_report: Callable[[dict, list[dict]], dict],
        limits: AgentLimits = AgentLimits(),
    ):
        self.model, self.tools, self.validate_report, self.limits = (
            model,
            tools,
            validate_report,
            limits,
        )

    async def run(
        self, context: dict, *, permitted: Callable[[], Awaitable[bool]], result=None
    ) -> AgentResult:
        result = result or AgentResult("running")
        try:
            async with asyncio.timeout(self.limits.timeout_seconds):
                await self._run(context, permitted, result)
        except TimeoutError:
            result.status, result.report = "timeout", None
        except InsufficientEvidence:
            result.status, result.report = "insufficient_evidence", None
        except asyncio.CancelledError:
            raise
        except Exception:
            result.status, result.report = "failed", None
        return result

    async def _run(self, context, permitted, result):
        import json

        queries = {}
        for _ in range(self.limits.rounds):
            if not await permitted():
                result.status = "disabled"
                return
            remaining = self.limits.tokens - result.tokens
            if remaining <= 0:
                result.status = "token_limit"
                return
            step = await self.model.step(context, list(result.trace), token_budget=remaining)
            result.steps.append({"at": datetime.now(UTC).isoformat(), "response": step})
            consumed = step.get("total_tokens")
            if not isinstance(consumed, int) or isinstance(consumed, bool) or consumed < 0:
                result.status = "usage_unknown"
                return
            result.tokens += consumed
            if result.tokens > self.limits.tokens:
                result.status = "token_limit"
                return
            if not await permitted():
                result.status = "disabled"
                return
            if step.get("action") == "finish":
                result.report = self.validate_report(step["report"], result.trace)
                result.status = "completed"
                return
            name, arguments = step.get("tool"), step.get("arguments")
            if name not in self.tools or not isinstance(arguments, dict):
                result.status = "invalid_tool"
                return
            key = json.dumps([name, arguments], sort_keys=True, ensure_ascii=False)
            queries[key] = queries.get(key, 0) + 1
            if queries[key] > self.limits.repeated_queries:
                result.status = "repeat_limit"
                return
            event = {
                "tool": name,
                "arguments": arguments,
                "started_at": datetime.now(UTC).isoformat(),
            }
            result.trace.append(event)
            try:
                event["evidence"] = await self.tools[name](arguments)
                event["status"] = "completed"
            except Exception:
                event["status"] = "unavailable"
            event["completed_at"] = datetime.now(UTC).isoformat()
        result.status = "round_limit"


async def optional_position_review(
    agent: ResearchAgent, context: dict, *, current_generation: Callable[[], Awaitable[int | None]]
) -> AgentResult:
    """None means off; a generation change invalidates in-flight work, including off/on."""
    generation = await current_generation()
    if generation is None:
        return AgentResult("disabled")

    async def permitted():
        return await current_generation() == generation

    result = AgentResult("running")
    task = asyncio.create_task(agent.run(context, permitted=permitted, result=result))

    async def watch():
        while await permitted():
            await asyncio.sleep(0.2)

    watcher = asyncio.create_task(watch())
    try:
        done, _ = await asyncio.wait({task, watcher}, return_when=asyncio.FIRST_COMPLETED)
        if task in done:
            result = await task
        else:
            result.status, result.report = "disabled", None
    finally:
        for pending in (task, watcher):
            if not pending.done():
                pending.cancel()
        await asyncio.gather(task, watcher, return_exceptions=True)
    if not await permitted():
        result.status, result.report = "disabled", None
    return result
