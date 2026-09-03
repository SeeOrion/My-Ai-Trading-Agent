from datetime import date
from decimal import Decimal

from ai_trading_agent.domain.aggregate.market import Instrument
from ai_trading_agent.domain.aggregate.research import (
    CapitalFlowSnapshot,
    FinancialSnapshot,
    OptionLeg,
    OptionStrategy,
    analyze_financial_sentiment,
    assess_capital_flow,
    assess_fundamentals,
    assess_option_strategy,
)
from ai_trading_agent.domain.enums.market import Market
from ai_trading_agent.domain.enums.research import (
    OptionKind,
    PositionSide,
    SentimentLabel,
)


def test_assesses_published_fundamentals_with_explainable_observations() -> None:
    snapshot = FinancialSnapshot(
        instrument=Instrument("600519.SH", Market.A_SHARE),
        announced_on=date(2026, 8, 30),
        report_period=date(2026, 6, 30),
        return_on_equity_pct=Decimal("18"),
        gross_margin_pct=Decimal("35"),
        current_ratio=Decimal("1.5"),
        net_profit_growth_pct=Decimal("12"),
        price_to_earnings=Decimal("25"),
        source="fixture",
    )

    assessment = assess_fundamentals(snapshot)

    assert assessment.score == 6
    assert "return on equity is at least 15%" in assessment.observations


def test_assesses_capital_and_large_order_flows_separately() -> None:
    snapshot = CapitalFlowSnapshot(
        Instrument("600519.SH", Market.A_SHARE),
        date(2026, 9, 1),
        net_flow_cny=Decimal("1000000"),
        large_order_net_flow_cny=Decimal("-200000"),
        source="fixture",
    )

    assessment = assess_capital_flow(snapshot)

    assert assessment.direction == "inflow"
    assert assessment.institutional_direction == "outflow"


def test_explainable_finance_sentiment_handles_chinese_text() -> None:
    assessment = analyze_financial_sentiment("公司盈利增长超预期，但面临诉讼风险")

    assert assessment.label == SentimentLabel.POSITIVE
    assert assessment.score == Decimal("0.5")


def test_long_call_payoff_and_break_even_are_exact() -> None:
    strategy = OptionStrategy(
        (OptionLeg(OptionKind.CALL, PositionSide.LONG, Decimal("100"), Decimal("2")),)
    )

    assessment = assess_option_strategy(strategy)

    assert strategy.expiry_pnl(Decimal("105")) == Decimal("300")
    assert assessment.break_evens == (Decimal("102"),)
    assert assessment.maximum_profit is None
    assert assessment.maximum_loss == Decimal("-200")
