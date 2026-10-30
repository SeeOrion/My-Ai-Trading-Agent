"""Request-local telemetry; never retain prompts, responses, URLs or credentials."""

import logging
from contextvars import ContextVar
from typing import Awaitable, Callable

UsageSink = Callable[[dict], Awaitable[None]]
usage_sink: ContextVar[UsageSink | None] = ContextVar("llm_usage_sink", default=None)
usage_feature: ContextVar[str] = ContextVar("llm_usage_feature", default="research")


def token_counts(body: dict) -> dict:
    usage = (body.get("usage") or {}) if isinstance(body, dict) else {}

    def count(value):
        return (
            value if isinstance(value, int) and not isinstance(value, bool) and value >= 0 else None
        )

    return {
        "input_tokens": count(usage.get("prompt_tokens")),
        "output_tokens": count(usage.get("completion_tokens")),
        "total_tokens": count(usage.get("total_tokens")),
        "cached_tokens": count((usage.get("prompt_tokens_details") or {}).get("cached_tokens")),
        "reasoning_tokens": count(
            (usage.get("completion_tokens_details") or {}).get("reasoning_tokens")
        ),
    }


async def record_usage(
    *, model: str, status: str, body: dict | None = None, reason: str = ""
) -> None:
    sink = usage_sink.get()
    if sink is None:
        return
    try:
        await sink(
            {
                "feature": usage_feature.get(),
                "model": model,
                "status": status,
                "reason": reason,
                **token_counts(body or {}),
            }
        )
    except Exception:
        # Telemetry failure must not turn a successful analysis into an error.
        logging.getLogger(__name__).warning("LLM usage persistence unavailable")
