from decimal import Decimal
from uuid import uuid4

import pytest

from ai_trading_agent.domain.aggregate.strategy import StrategyProfile
from ai_trading_agent.domain.enums.market import Market


def test_strategy_profile_is_versioned_declarative_research_preference() -> None:
    profile = StrategyProfile(
        strategy_id=uuid4(),
        name="Quality momentum",
        thesis="Prefer quality names with positive news confirmation.",
        factor_ids=("momentum_20d", "return_on_equity"),
        markets=(Market.A_SHARE,),
        max_position_pct=Decimal("10"),
        risk_notes="Diversify.",
        status="active",
    )

    assert profile.definition()["factor_ids"] == ["momentum_20d", "return_on_equity"]
    assert profile.version == 1


def test_strategy_profile_rejects_duplicate_factor_injection() -> None:
    with pytest.raises(ValueError, match="must not contain duplicates"):
        StrategyProfile(
            strategy_id=uuid4(),
            name="Invalid",
            thesis="A valid thesis with a duplicate factor.",
            factor_ids=("momentum_20d", "momentum_20d"),
            markets=(Market.A_SHARE,),
            max_position_pct=Decimal("10"),
            risk_notes="",
        )
