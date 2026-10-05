"""In-process scheduler for bounded private-server market scans."""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Awaitable, Callable

_logger = logging.getLogger(__name__)


class RecurringTaskScheduler:
    """Run one bounded callback at an interval without blocking API traffic."""

    def __init__(
        self,
        callback: Callable[[], Awaitable[None]],
        interval_seconds: int,
        *,
        run_immediately: bool = True,
        align_to_interval_boundary: bool = False,
    ) -> None:
        self._callback = callback
        self._interval_seconds = interval_seconds
        self._run_immediately = run_immediately
        self._align_to_interval_boundary = align_to_interval_boundary
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
        if not self._run_immediately:
            try:
                await asyncio.wait_for(
                    self._stop_requested.wait(), timeout=self._first_wait_seconds()
                )
            except TimeoutError:
                pass
        while not self._stop_requested.is_set():
            try:
                await self._callback()
            except Exception:
                # Individual failed runs are persisted by the use case. Keep the
                # traceback in the service log if setup fails before persistence.
                _logger.exception("Recurring task callback failed; next cycle will continue")
            try:
                wait_seconds = (
                    self._seconds_until_next_boundary()
                    if self._align_to_interval_boundary
                    else self._interval_seconds
                )
                await asyncio.wait_for(
                    self._stop_requested.wait(), timeout=wait_seconds
                )
            except TimeoutError:
                continue

    def _first_wait_seconds(self) -> float:
        """Align periodic production jobs to a wall-clock interval when requested."""
        if not self._align_to_interval_boundary:
            return self._interval_seconds
        return self._seconds_until_next_boundary()

    def _seconds_until_next_boundary(self) -> float:
        """Re-align after every callback so task duration cannot accumulate drift."""
        remainder = time.time() % self._interval_seconds
        delay = self._interval_seconds - remainder
        return self._interval_seconds if delay < 0.01 else delay


# Compatibility name for deployments that imported the first scheduler directly.
MarketScanScheduler = RecurringTaskScheduler
