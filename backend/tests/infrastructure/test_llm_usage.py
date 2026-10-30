from unittest.mock import AsyncMock

import pytest

from ai_trading_agent.infrastructure.rpc.llm_usage import record_usage, token_counts, usage_sink


def test_reported_total_does_not_double_count_reasoning_or_cached_input():
    counts = token_counts(
        {
            "usage": {
                "prompt_tokens": 100,
                "completion_tokens": 40,
                "total_tokens": 140,
                "prompt_tokens_details": {"cached_tokens": 60},
                "completion_tokens_details": {"reasoning_tokens": 30},
            }
        }
    )
    assert counts == dict(
        input_tokens=100, output_tokens=40, total_tokens=140, cached_tokens=60, reasoning_tokens=30
    )
    assert all(value is None for value in token_counts({}).values())


@pytest.mark.asyncio
async def test_usage_contains_no_request_body_or_secret_and_failure_is_nonfatal():
    sink = AsyncMock()
    token = usage_sink.set(sink)
    try:
        await record_usage(
            model="test", status="success", body={"choices": ["private"], "api_key": "secret"}
        )
        event = sink.call_args.args[0]
        assert "secret" not in str(event) and "private" not in str(event)
        sink.side_effect = RuntimeError("database unavailable")
        await record_usage(model="test", status="failed")
    finally:
        usage_sink.reset(token)
