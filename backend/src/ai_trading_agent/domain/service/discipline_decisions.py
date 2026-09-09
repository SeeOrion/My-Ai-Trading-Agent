"""Pure price-discipline rules.

The priority is deliberately conservative: risk exit, profit taking, adding,
then a possible initial entry.  This module has no provider, database, LLM or
brokerage dependency so the result can be audited and tested exactly.
"""

from __future__ import annotations

from ai_trading_agent.domain.aggregate.discipline import TradingDiscipline
from ai_trading_agent.domain.aggregate.discipline_decision import DisciplineDecision
from ai_trading_agent.domain.aggregate.market import Quote
from ai_trading_agent.domain.enums.research import DisciplineDecisionStatus


def evaluate_discipline(
    discipline: TradingDiscipline,
    quote: Quote,
) -> DisciplineDecision:
    """Evaluate one active plan against its exact instrument's latest quote."""
    if discipline.instrument != quote.instrument:
        raise ValueError("discipline and quote must refer to the same instrument")

    price = quote.last_price
    if price <= discipline.exit_price:
        return DisciplineDecision(
            discipline, DisciplineDecisionStatus.EXIT, price, discipline.exit_price
        )
    if price >= discipline.take_profit_price:
        return DisciplineDecision(
            discipline,
            DisciplineDecisionStatus.TAKE_PROFIT,
            price,
            discipline.take_profit_price,
        )
    if discipline.add_price is not None and price >= discipline.add_price:
        return DisciplineDecision(
            discipline,
            DisciplineDecisionStatus.ADD_CONDITION_MET,
            price,
            discipline.add_price,
        )
    if price <= discipline.buy_price:
        return DisciplineDecision(
            discipline,
            DisciplineDecisionStatus.BUY_CANDIDATE,
            price,
            discipline.buy_price,
        )
    return DisciplineDecision(discipline, DisciplineDecisionStatus.OBSERVE, price, None)
