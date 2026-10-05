from ai_trading_agent.interfaces.task import market_scans
from ai_trading_agent.interfaces.task.market_scans import RecurringTaskScheduler


async def _no_op() -> None:
    return None


def test_aligned_scheduler_recomputes_the_next_wall_clock_boundary(monkeypatch) -> None:
    scheduler = RecurringTaskScheduler(
        _no_op,
        600,
        run_immediately=False,
        align_to_interval_boundary=True,
    )

    monkeypatch.setattr(market_scans.time, "time", lambda: 12_301.0)
    assert scheduler._first_wait_seconds() == 299.0

    monkeypatch.setattr(market_scans.time, "time", lambda: 12_427.0)
    assert scheduler._seconds_until_next_boundary() == 173.0
