from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

from ai_trading_agent.domain.aggregate.discipline import TradingDiscipline
from ai_trading_agent.domain.aggregate.market import Instrument, Quote
from ai_trading_agent.domain.enums.market import Market
from ai_trading_agent.domain.service.discipline_decisions import evaluate_discipline
from ai_trading_agent.domain.service.discipline_entry import disciplined_entry_blockers


def _decision(price: str):
    discipline = TradingDiscipline(
        discipline_id=uuid4(),
        name="回撤买入纪律",
        instrument=Instrument("600519.SH", Market.A_SHARE),
        buy_price=Decimal("15"),
        add_price=None,
        take_profit_price=Decimal("16.5"),
        exit_price=Decimal("14.5"),
    )
    return evaluate_discipline(
        discipline,
        Quote(
            instrument=discipline.instrument,
            last_price=Decimal(price),
            observed_at=datetime.now(UTC),
            source="test",
        ),
    )


def test_strict_discipline_entry_requires_an_applicable_buy_signal() -> None:
    assert disciplined_entry_blockers([])
    assert disciplined_entry_blockers([_decision("15")]) == ()
    assert "未满足买入条件" in disciplined_entry_blockers([_decision("16")])[0]
