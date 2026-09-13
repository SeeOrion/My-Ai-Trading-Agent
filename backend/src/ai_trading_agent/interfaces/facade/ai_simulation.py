"""Composition layer for the auditable AI paper-trading simulator."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID, uuid4

from fastapi import FastAPI

from ai_trading_agent.application.strategies import ListStrategiesHandler
from ai_trading_agent.domain.aggregate.ai_simulation import (
    AiSimulationDecisionReport,
    AiSimulationOverview,
    AiSimulationPortfolio,
    AiSimulationPosition,
    AiSimulationPositionValuation,
    AiSimulationTrade,
)
from ai_trading_agent.domain.aggregate.strategy import StrategyProfile
from ai_trading_agent.domain.aggregate.watchlist import PaperPosition
from ai_trading_agent.domain.enums.candidates import CandidateRanking
from ai_trading_agent.domain.enums.market import Market
from ai_trading_agent.domain.service.ai_simulation import (
    AiSimulationCandidate,
    AiSimulationEntryDecision,
    evaluate_simulated_entry,
    reconfigure_simulation_portfolio,
)
from ai_trading_agent.infrastructure.repo.ai_simulation import SqlAlchemyAiSimulationRepository
from ai_trading_agent.interfaces.facade.instruments import resolve_instrument_identity
from ai_trading_agent.interfaces.facade.persistence import private_session_factory
from ai_trading_agent.interfaces.facade.portfolio import paper_portfolio_overview
from ai_trading_agent.interfaces.facade.research_workspace import (
    builtin_factor_analysis,
    strategy_repository,
    today_candidates,
)


@dataclass(frozen=True, slots=True)
class AiSimulationRunRequest:
    market: Market
    initial_capital: Decimal
    max_positions: int = 3
    strategy_id: UUID | None = None


def ai_simulation_repository(app: FastAPI) -> SqlAlchemyAiSimulationRepository:
    return SqlAlchemyAiSimulationRepository(private_session_factory(app))


async def run_ai_simulation(
    app: FastAPI, request: AiSimulationRunRequest
) -> AiSimulationOverview:
    """Run one bounded, deterministic AI paper-trading review for one market."""
    repository = ai_simulation_repository(app)
    strategy = await _select_strategy(app, request.market, request.strategy_id)
    _ensure_requested_strategy(request.strategy_id, strategy)
    portfolio = await repository.get_active(request.market)
    if portfolio is None:
        portfolio = AiSimulationPortfolio(
            portfolio_id=uuid4(),
            market=request.market.value,
            currency=_currency_for_market(request.market),
            initial_capital=request.initial_capital,
            cash_balance=request.initial_capital,
            max_positions=request.max_positions,
            strategy_id=None if strategy is None else strategy.strategy_id,
        )
        portfolio = await repository.save_portfolio(portfolio)
        positions: list[AiSimulationPosition] = []
    else:
        positions = await repository.list_open_positions(portfolio.portfolio_id)
        portfolio = await _save_reconfigured_portfolio(
            repository, portfolio, positions, request, strategy
        )
    screen, _ = await today_candidates(
        request.market, CandidateRanking.BALANCED_ENTRY, refresh=True
    )
    existing_symbols = {item.instrument.symbol for item in positions}
    notices: list[str] = [
        "AI 模拟组合仅在预设高流动性研究样本中筛选，不是全市场扫描，也不会发送真实订单。"
    ]
    if strategy is None:
        notices.append("未选择匹配的启用策略：使用内置因子与 25% 单标的风险预算。")
    else:
        notices.append(f"本轮采用策略「{strategy.name}」，仅参考其已配置的因子与仓位上限。")

    decision_reports: list[AiSimulationDecisionReport] = []

    for candidate in screen.candidates:
        if candidate.observation.instrument.symbol in existing_symbols:
            decision_reports.append(
                AiSimulationDecisionReport(
                    symbol=candidate.observation.instrument.symbol,
                    display_name=candidate.observation.name,
                    score=candidate.score,
                    decision="already_held",
                    supportive_factor_count=0,
                    adverse_factor_count=0,
                    available_factor_ids=(),
                    unavailable_factor_ids=(),
                    blockers=("该标的已经在 AI 模拟组合中，本轮不重复建仓。",),
                )
            )
            continue
        analysis = await builtin_factor_analysis(
            candidate.observation.instrument,
            financial_snapshot=None,
            news_sentiment=None,
        )
        simulated_candidate = _candidate_from_analysis(candidate, analysis, strategy)
        decision = evaluate_simulated_entry(
            simulated_candidate,
            available_cash=portfolio.cash_balance,
            initial_capital=portfolio.initial_capital,
            open_position_count=len(positions),
            max_positions=portfolio.max_positions,
            max_position_percent=(strategy.max_position_pct if strategy else Decimal("25")),
            lot_size=Decimal("100") if request.market is Market.A_SHARE else Decimal("1"),
        )
        decision_reports.append(_decision_report(simulated_candidate, decision))
        allocation = decision.allocation
        if allocation is None:
            continue
        position = AiSimulationPosition(
            position_id=uuid4(),
            portfolio_id=portfolio.portfolio_id,
            instrument=candidate.observation.instrument,
            quantity=allocation.quantity,
            average_cost=candidate.observation.last_price,
            opened_at=datetime.now(UTC),
            candidate_score=candidate.score,
            factor_context=simulated_candidate.available_factor_ids,
            rationale=allocation.rationale,
        )
        await repository.save_position(position)
        await repository.save_trade(
            AiSimulationTrade(
                trade_id=uuid4(),
                portfolio_id=portfolio.portfolio_id,
                position_id=position.position_id,
                side="buy",
                quantity=position.quantity,
                price=position.average_cost,
                executed_at=position.opened_at,
                rationale=position.rationale,
            )
        )
        portfolio = AiSimulationPortfolio(
            portfolio_id=portfolio.portfolio_id,
            market=portfolio.market,
            currency=portfolio.currency,
            initial_capital=portfolio.initial_capital,
            cash_balance=portfolio.cash_balance - allocation.amount,
            max_positions=portfolio.max_positions,
            strategy_id=portfolio.strategy_id,
        )
        portfolio = await repository.save_portfolio(portfolio)
        positions.append(position)
        existing_symbols.add(position.instrument.symbol)
        if len(positions) >= portfolio.max_positions:
            break

    overview = await ai_simulation_overview(app, request.market)
    return AiSimulationOverview(
        portfolio=overview.portfolio,
        observed_at=overview.observed_at,
        positions=overview.positions,
        invested_cost=overview.invested_cost,
        market_value=overview.market_value,
        total_equity=overview.total_equity,
        cumulative_pnl=overview.cumulative_pnl,
        daily_pnl=overview.daily_pnl,
        month_to_date_pnl=overview.month_to_date_pnl,
        notices=tuple(dict.fromkeys((*overview.notices, *notices))),
        decision_reports=tuple(decision_reports),
    )


async def update_ai_simulation_settings(
    app: FastAPI, request: AiSimulationRunRequest
) -> AiSimulationOverview:
    """Persist account settings without running a candidate screen or trade cycle."""
    repository = ai_simulation_repository(app)
    portfolio = await repository.get_active(request.market)
    if portfolio is None:
        raise LookupError("尚未创建该市场的 AI 模拟组合")
    strategy = await _select_strategy(app, request.market, request.strategy_id)
    _ensure_requested_strategy(request.strategy_id, strategy)
    positions = await repository.list_open_positions(portfolio.portfolio_id)
    await _save_reconfigured_portfolio(repository, portfolio, positions, request, strategy)
    overview = await ai_simulation_overview(app, request.market)
    return AiSimulationOverview(
        portfolio=overview.portfolio,
        observed_at=overview.observed_at,
        positions=overview.positions,
        invested_cost=overview.invested_cost,
        market_value=overview.market_value,
        total_equity=overview.total_equity,
        cumulative_pnl=overview.cumulative_pnl,
        daily_pnl=overview.daily_pnl,
        month_to_date_pnl=overview.month_to_date_pnl,
        notices=tuple(
            dict.fromkeys(
                (*overview.notices, "AI 模拟账户设置已同步；既有持仓和交易记录已保留。")
            )
        ),
    )


async def ai_simulation_overview(app: FastAPI, market: Market) -> AiSimulationOverview:
    repository = ai_simulation_repository(app)
    portfolio = await repository.get_active(market)
    if portfolio is None:
        raise LookupError("尚未创建该市场的 AI 模拟组合")
    positions = await repository.list_open_positions(portfolio.portfolio_id)
    paper_positions = [
        PaperPosition(
            position_id=item.position_id,
            instrument=item.instrument,
            quantity=item.quantity,
            average_cost=item.average_cost,
            notes="AI 模拟交易持仓",
        )
        for item in positions
    ]
    paper_overview = await paper_portfolio_overview(paper_positions)
    by_id = {item.position.position_id: item for item in paper_overview.valuations}
    display_names = await _display_names(positions)
    valued_positions = tuple(
        _position_valuation(
            position,
            by_id.get(position.position_id),
            display_names.get(position.position_id),
        )
        for position in positions
    )
    summary = next(
        (
            item
            for item in paper_overview.summary.currencies
            if item.currency == portfolio.currency
        ),
        None,
    )
    invested_cost = sum((item.cost_amount for item in positions), Decimal("0"))
    market_value = Decimal("0") if summary is None else summary.total_market_value
    total_equity = portfolio.cash_balance + market_value
    return AiSimulationOverview(
        portfolio=portfolio,
        observed_at=paper_overview.summary.observed_at,
        positions=valued_positions,
        invested_cost=invested_cost,
        market_value=market_value,
        total_equity=total_equity,
        cumulative_pnl=total_equity - portfolio.initial_capital,
        daily_pnl=None if summary is None else summary.daily_pnl,
        month_to_date_pnl=None if summary is None else summary.month_to_date_pnl,
        notices=paper_overview.notices,
    )


async def _select_strategy(
    app: FastAPI, market: Market, strategy_id: UUID | None
) -> StrategyProfile | None:
    strategies = await ListStrategiesHandler(strategy_repository(app)).handle()
    if strategy_id is None:
        return None
    return next(
        (
            item
            for item in strategies
            if (
                item.strategy_id == strategy_id
                and item.status == "active"
                and market in item.markets
            )
        ),
        None,
    )


def _ensure_requested_strategy(
    strategy_id: UUID | None, strategy: StrategyProfile | None
) -> None:
    if strategy_id is not None and strategy is None:
        raise ValueError("所选策略不存在、未启用，或不适用于当前市场。")


async def _save_reconfigured_portfolio(
    repository: SqlAlchemyAiSimulationRepository,
    portfolio: AiSimulationPortfolio,
    positions: list[AiSimulationPosition],
    request: AiSimulationRunRequest,
    strategy: StrategyProfile | None,
) -> AiSimulationPortfolio:
    updated = reconfigure_simulation_portfolio(
        portfolio,
        initial_capital=request.initial_capital,
        max_positions=request.max_positions,
        strategy_id=None if strategy is None else strategy.strategy_id,
        open_position_count=len(positions),
    )
    return portfolio if updated == portfolio else await repository.save_portfolio(updated)


def _candidate_from_analysis(
    candidate, analysis: dict[str, object], strategy: StrategyProfile | None
) -> AiSimulationCandidate:  # type: ignore[no-untyped-def]
    observations = tuple(analysis["observations"])
    requested = set(strategy.factor_ids) if strategy is not None else None
    relevant = tuple(
        item for item in observations if requested is None or item["identifier"] in requested
    )
    available = tuple(
        str(item["identifier"])
        for item in relevant
        if item["direction"] != "unavailable"
    )
    unavailable = tuple(
        str(item["identifier"])
        for item in relevant
        if item["direction"] == "unavailable"
    )
    supportive = sum(item["direction"] == "supportive" for item in relevant)
    adverse = sum(item["direction"] == "adverse" for item in relevant)
    rationale = tuple(
        str(item["interpretation"])
        for item in relevant
        if item["direction"] == "supportive"
    ) or tuple(candidate.reasons)
    return AiSimulationCandidate(
        symbol=candidate.observation.instrument.symbol,
        display_name=candidate.observation.name,
        score=candidate.score,
        last_price=candidate.observation.last_price,
        supportive_factor_count=supportive,
        adverse_factor_count=adverse,
        available_factor_ids=available,
        unavailable_factor_ids=unavailable,
        rationale=rationale,
    )


def _currency_for_market(market: Market) -> str:
    return {Market.A_SHARE: "CNY", Market.HONG_KONG: "HKD", Market.UNITED_STATES: "USD"}[market]


def _decision_report(
    candidate: AiSimulationCandidate,
    decision: AiSimulationEntryDecision,
) -> AiSimulationDecisionReport:
    return AiSimulationDecisionReport(
        symbol=candidate.symbol,
        display_name=candidate.display_name,
        score=candidate.score,
        decision="buy" if decision.allocation is not None else "skip",
        supportive_factor_count=candidate.supportive_factor_count,
        adverse_factor_count=candidate.adverse_factor_count,
        available_factor_ids=candidate.available_factor_ids,
        unavailable_factor_ids=candidate.unavailable_factor_ids,
        blockers=decision.blockers,
    )


def _position_valuation(
    position: AiSimulationPosition, valuation, display_name: str | None
) -> AiSimulationPositionValuation:  # type: ignore[no-untyped-def]
    if valuation is None:
        return AiSimulationPositionValuation(
            position=position,
            display_name=display_name,
            last_price=None,
            market_value=None,
            unrealized_pnl=None,
            unrealized_pnl_percent=None,
            daily_pnl=None,
            month_to_date_pnl=None,
            source=None,
        )
    return AiSimulationPositionValuation(
        position=position,
        display_name=display_name,
        last_price=valuation.quote.last_price,
        market_value=valuation.market_value,
        unrealized_pnl=valuation.unrealized_pnl,
        unrealized_pnl_percent=valuation.unrealized_pnl_percent,
        daily_pnl=valuation.daily_pnl,
        month_to_date_pnl=valuation.month_to_date_pnl,
        source=valuation.quote.source,
    )


async def _display_names(
    positions: list[AiSimulationPosition],
) -> dict[UUID, str | None]:
    async def resolve(position: AiSimulationPosition) -> tuple[UUID, str | None]:
        try:
            identity = await resolve_instrument_identity(position.instrument)
            return position.position_id, None if identity is None else identity.display_name
        except Exception:
            return position.position_id, None

    resolved = await asyncio.gather(*(resolve(position) for position in positions))
    return dict(resolved)
