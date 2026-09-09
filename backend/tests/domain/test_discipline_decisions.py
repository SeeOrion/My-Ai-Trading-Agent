from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

import pytest

from ai_trading_agent.domain.aggregate.discipline import TradingDiscipline
from ai_trading_agent.domain.aggregate.market import Instrument, Quote
from ai_trading_agent.domain.enums.market import Market
from ai_trading_agent.domain.enums.research import DisciplineDecisionStatus
from ai_trading_agent.domain.service.discipline_decisions import evaluate_discipline


@pytest.fixture
def discipline() -> TradingDiscipline:
    return TradingDiscipline(
        discipline_id=uuid4(),
        name="示例纪律",
        instrument=Instrument("600519.SH", Market.A_SHARE),
        buy_price=Decimal("15"),
        add_price=Decimal("16"),
        take_profit_price=Decimal("16.5"),
        exit_price=Decimal("14.5"),
    )


@pytest.mark.parametrize(
    ("price", "expected"),
    [
        ("14.5", DisciplineDecisionStatus.EXIT),
        ("15", DisciplineDecisionStatus.BUY_CANDIDATE),
        ("15.4", DisciplineDecisionStatus.OBSERVE),
        ("16", DisciplineDecisionStatus.ADD_CONDITION_MET),
        ("16.5", DisciplineDecisionStatus.TAKE_PROFIT),
    ],
)
def test_price_discipline_has_conservative_boundary_priority(
    discipline: TradingDiscipline,
    price: str,
    expected: DisciplineDecisionStatus,
) -> None:
    quote = Quote(
        instrument=discipline.instrument,
        last_price=Decimal(price),
        observed_at=datetime.now(UTC),
        source="test",
    )

    assert evaluate_discipline(discipline, quote).status is expected


def test_discipline_cannot_be_evaluated_with_a_different_instrument(
    discipline: TradingDiscipline,
) -> None:
    quote = Quote(
        instrument=Instrument("000001.SZ", Market.A_SHARE),
        last_price=Decimal("10"),
        observed_at=datetime.now(UTC),
        source="test",
    )

    with pytest.raises(ValueError, match="same instrument"):
        evaluate_discipline(discipline, quote)
