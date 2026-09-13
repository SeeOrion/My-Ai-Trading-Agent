from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

from ai_trading_agent.domain.aggregate.discipline import TradingDiscipline
from ai_trading_agent.domain.aggregate.market import Instrument, Quote
from ai_trading_agent.domain.aggregate.strategy import StrategyProfile
from ai_trading_agent.domain.enums.market import Market
from ai_trading_agent.domain.enums.research import DisciplineStatus, ManualActionStatus
from ai_trading_agent.domain.service.discipline_decisions import evaluate_discipline
from ai_trading_agent.domain.service.manual_actions import assess_manual_action


def _discipline() -> TradingDiscipline:
    return TradingDiscipline(
        discipline_id=uuid4(),
        name="回撤建仓计划",
        instrument=Instrument("600519.SH", Market.A_SHARE),
        buy_price=Decimal("15"),
        add_price=Decimal("16"),
        take_profit_price=Decimal("16.5"),
        exit_price=Decimal("14.5"),
        status=DisciplineStatus.ACTIVE,
    )


def _strategy() -> StrategyProfile:
    return StrategyProfile(
        strategy_id=uuid4(),
        name="质量动量策略",
        thesis="质量与趋势一致时才考虑建仓。",
        factor_ids=("momentum_20d", "return_on_equity"),
        markets=(Market.A_SHARE,),
        max_position_pct=Decimal("20"),
        risk_notes="仅按个人纪律价位复核。",
        status="active",
    )


def _quote(price: str) -> Quote:
    instrument = Instrument("600519.SH", Market.A_SHARE)
    return Quote(
        instrument=instrument,
        last_price=Decimal(price),
        observed_at=datetime.now(UTC),
        source="fixture",
    )


def test_entry_requires_matching_strategy_and_supportive_selected_factors() -> None:
    result = assess_manual_action(
        {"momentum_20d": "supportive", "return_on_equity": "neutral"},
        [_strategy()],
        [evaluate_discipline(_discipline(), _quote("15"))],
    )

    assert result.status is ManualActionStatus.CONSIDER_ENTRY
    assert result.price_level == Decimal("15")
    assert result.max_position_pct == Decimal("20")


def test_entry_price_is_held_at_observe_when_strategy_factor_is_adverse() -> None:
    result = assess_manual_action(
        {"momentum_20d": "adverse", "return_on_equity": "neutral"},
        [_strategy()],
        [evaluate_discipline(_discipline(), _quote("15"))],
    )

    assert result.status is ManualActionStatus.OBSERVE
    assert result.price_level == Decimal("15")


def test_exit_discipline_overrides_strategy_factor_direction() -> None:
    result = assess_manual_action(
        {"momentum_20d": "supportive", "return_on_equity": "supportive"},
        [_strategy()],
        [evaluate_discipline(_discipline(), _quote("14.5"))],
    )

    assert result.status is ManualActionStatus.EXIT_REVIEW
    assert result.price_level == Decimal("14.5")
