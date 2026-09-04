from decimal import Decimal
from uuid import uuid4

import pytest

from ai_trading_agent.domain.aggregate.discipline import TradingDiscipline
from ai_trading_agent.domain.aggregate.market import Instrument
from ai_trading_agent.domain.enums.market import Market


def test_trading_discipline_keeps_a_declarative_price_plan() -> None:
    discipline = TradingDiscipline(
        discipline_id=uuid4(),
        name="贵州茅台分批建仓",
        instrument=Instrument("600519.SH", Market.A_SHARE),
        buy_price=Decimal("15"),
        add_price=Decimal("16"),
        take_profit_price=Decimal("16.5"),
        exit_price=Decimal("14.5"),
    )

    assert discipline.definition()["take_profit_price"] == "16.5"


def test_trading_discipline_rejects_conflicting_price_levels() -> None:
    with pytest.raises(ValueError, match="add_price"):
        TradingDiscipline(
            discipline_id=uuid4(),
            name="无效纪律",
            instrument=Instrument("600519.SH", Market.A_SHARE),
            buy_price=Decimal("15"),
            add_price=Decimal("16.5"),
            take_profit_price=Decimal("16"),
            exit_price=Decimal("14.5"),
        )
