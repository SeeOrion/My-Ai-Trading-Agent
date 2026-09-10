"""In-process scheduler for bounded private-server market scans."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable


class RecurringTaskScheduler:
    """Run one bounded callback at an interval without blocking API traffic."""

    def __init__(self, callback: Callable[[], Awaitable[None]], interval_seconds: int) -> None:
        self._callback = callback
        self._interval_seconds = interval_seconds
        self._stop_requested = asyncio.Event()
        self._task: asyncio.Task[None] | None = None

    def start(self) -> None:
        if self._task is None:
            self._task = asyncio.create_task(self._run(), name="recurring-private-task")

    async def stop(self) -> None:
        self._stop_requested.set()
        if self._task is not None:
            await self._task

    async def _run(self) -> None:
        while not self._stop_requested.is_set():
            try:
                await self._callback()
            except Exception:
                # Individual failed runs are persisted by the use case. A database
                # outage should not terminate the scheduler forever.
                pass
            try:
                await asyncio.wait_for(
                    self._stop_requested.wait(), timeout=self._interval_seconds
                )
            except TimeoutError:
                continue


# Compatibility name for deployments that imported the first scheduler directly.
MarketScanScheduler = RecurringTaskScheduler
