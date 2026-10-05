"""Composition layer for the auditable AI paper-trading simulator."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID, uuid4

from fastapi import FastAPI

from ai_trading_agent.application.strategies import ListStrategiesHandler
from ai_trading_agent.domain.ability.trading_calendar import TradingCalendarPort
from ai_trading_agent.domain.aggregate.ai_simulation import (
    AiSimulationDecisionReport,
    AiSimulationOverview,
    AiSimulationPortfolio,
    AiSimulationPosition,
    AiSimulationPositionValuation,
    AiSimulationRun,
    AiSimulationTrade,
)
from ai_trading_agent.domain.aggregate.market import Quote
from ai_trading_agent.domain.aggregate.strategy import StrategyProfile
from ai_trading_agent.domain.aggregate.technical import calculate_indicators
from ai_trading_agent.domain.aggregate.watchlist import PaperPosition
from ai_trading_agent.domain.enums.candidates import CandidateRanking
from ai_trading_agent.domain.enums.market import Market
from ai_trading_agent.domain.enums.research import DisciplineDecisionStatus
from ai_trading_agent.domain.service.ai_simulation import (
    AiSimulationCandidate,
    AiSimulationEntryDecision,
    evaluate_simulated_entry,
    reconfigure_simulation_portfolio,
)
from ai_trading_agent.domain.service.discipline_entry import disciplined_entry_blockers
from ai_trading_agent.domain.service.factor_analysis import analyze_builtin_factors
from ai_trading_agent.domain.service.simulated_execution import (
    estimate_simulated_execution,
    minimum_trade_unit,
)
from ai_trading_agent.domain.service.simulation_exit import (
    EXIT_POLICY_VERSION,
    SimulationExitDecision,
    SimulationExitEvidence,
    evaluate_simulation_exit,
)
from ai_trading_agent.infrastructure.market_data.exchange_calendar import ExchangeTradingCalendar
from ai_trading_agent.infrastructure.repo.ai_simulation import SqlAlchemyAiSimulationRepository
from ai_trading_agent.interfaces.facade.disciplines import evaluate_active_disciplines
from ai_trading_agent.interfaces.facade.instruments import resolve_instrument_identity
from ai_trading_agent.interfaces.facade.persistence import private_session_factory
from ai_trading_agent.interfaces.facade.portfolio import paper_portfolio_overview
from ai_trading_agent.interfaces.facade.research_workspace import (
    builtin_factor_analysis,
    historical_bars_provider,
    latest_quote,
    strategy_repository,
    today_candidates,
)


@dataclass(frozen=True, slots=True)
class AiSimulationRunRequest:
    market: Market
    initial_capital: Decimal
    max_positions: int = 3
    strategy_ids: tuple[UUID, ...] = ()
    trigger: str = "manual"


def ai_simulation_repository(app: FastAPI) -> SqlAlchemyAiSimulationRepository:
    return SqlAlchemyAiSimulationRepository(private_session_factory(app))


async def run_ai_simulation(app: FastAPI, request: AiSimulationRunRequest) -> AiSimulationOverview:
    """Run one bounded, deterministic AI paper-trading review for one market."""
    started_at = datetime.now(UTC)
    repository = ai_simulation_repository(app)
    strategies = await _select_strategies(app, request.market, request.strategy_ids)
    _ensure_requested_strategies(request.strategy_ids, strategies)
    portfolio = await repository.get_active(request.market)
    if portfolio is None:
        portfolio = AiSimulationPortfolio(
            portfolio_id=uuid4(),
            market=request.market.value,
            currency=_currency_for_market(request.market),
            initial_capital=request.initial_capital,
            cash_balance=request.initial_capital,
            max_positions=request.max_positions,
            strategy_ids=tuple(item.strategy_id for item in strategies),
        )
        portfolio = await repository.save_portfolio(portfolio)
        positions: list[AiSimulationPosition] = []
    else:
        positions = await repository.list_open_positions(portfolio.portfolio_id)
        portfolio = await _save_reconfigured_portfolio(
            repository, portfolio, positions, request, strategies
        )
    portfolio, positions, discipline_notices = await _apply_position_exits(
        app, repository, portfolio, positions, strategies
    )
    screen, _ = await today_candidates(
        request.market, CandidateRanking.BALANCED_ENTRY, refresh=True
    )
    existing_symbols = {item.instrument.symbol for item in positions}
    notices: list[str] = [
        "AI 模拟组合仅在预设高流动性研究样本中筛选，不是全市场扫描，也不会发送真实订单。",
        (
            "模拟成交按最新参考价叠加 5bp 不利滑点和 5bp 成本估算记账；"
            "实际市场成交、税费与券商规则可能不同。"
        ),
        *discipline_notices,
    ]
    if not strategies:
        notices.append("未选择匹配的启用策略：使用内置因子与 25% 单标的风险预算。")
    else:
        notices.append(
            "本轮联合采用策略「"
            f"{'」、「'.join(item.name for item in strategies)}」，"
            "仅参考所选策略的因子，并按其中最严格的仓位上限分配。"
        )
    notices.append(
        "个人纪律为可选硬性约束：未配置适用纪律时按因子、策略和风险预算判断；"
        "配置并启用后，必须满足纪律买入条件才允许模拟建仓。"
    )

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
        simulated_candidate = _candidate_from_analysis(candidate, analysis, strategies)
        decision = evaluate_simulated_entry(
            simulated_candidate,
            available_cash=portfolio.cash_balance,
            initial_capital=portfolio.initial_capital,
            open_position_count=len(positions),
            max_positions=portfolio.max_positions,
            max_position_percent=_max_position_percent(strategies),
            lot_size=minimum_trade_unit(candidate.observation.instrument),
        )
        discipline_blockers = await _discipline_entry_blockers(app, candidate)
        if discipline_blockers:
            decision = AiSimulationEntryDecision(
                allocation=None,
                blockers=tuple(dict.fromkeys((*discipline_blockers, *decision.blockers))),
            )
        decision_reports.append(_decision_report(simulated_candidate, decision))
        allocation = decision.allocation
        if allocation is None:
            continue
        execution = estimate_simulated_execution(
            side="buy",
            reference_price=candidate.observation.last_price,
            quantity=allocation.quantity,
        )
        position = AiSimulationPosition(
            position_id=uuid4(),
            portfolio_id=portfolio.portfolio_id,
            instrument=candidate.observation.instrument,
            quantity=allocation.quantity,
            average_cost=execution.cash_required / allocation.quantity,
            opened_at=datetime.now(UTC),
            candidate_score=candidate.score,
            factor_context=simulated_candidate.available_factor_ids,
            rationale=tuple((*allocation.rationale, *execution.rationale)),
            highest_price=execution.fill_price,
        )
        await repository.save_position(position)
        await repository.save_trade(
            AiSimulationTrade(
                trade_id=uuid4(),
                portfolio_id=portfolio.portfolio_id,
                position_id=position.position_id,
                side="buy",
                quantity=position.quantity,
                price=execution.fill_price,
                executed_at=position.opened_at,
                rationale=position.rationale,
            )
        )
        portfolio = AiSimulationPortfolio(
            portfolio_id=portfolio.portfolio_id,
            market=portfolio.market,
            currency=portfolio.currency,
            initial_capital=portfolio.initial_capital,
            cash_balance=portfolio.cash_balance - execution.cash_required,
            max_positions=portfolio.max_positions,
            strategy_ids=portfolio.strategy_ids,
        )
        portfolio = await repository.save_portfolio(portfolio)
        positions.append(position)
        existing_symbols.add(position.instrument.symbol)
        if len(positions) >= portfolio.max_positions:
            break

    unavailable_factor_ids = tuple(
        dict.fromkeys(
            factor_id for report in decision_reports for factor_id in report.unavailable_factor_ids
        )
    )
    if unavailable_factor_ids:
        notices.append(
            "本轮存在数据缺口："
            f"{'、'.join(unavailable_factor_ids)}。缺失因子仅作提示，不会单独阻止模拟建仓。"
        )

    overview = await ai_simulation_overview(app, request.market)
    result = AiSimulationOverview(
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
    await repository.save_run(
        AiSimulationRun(
            run_id=uuid4(),
            portfolio_id=result.portfolio.portfolio_id,
            market=request.market,
            trigger=request.trigger,
            status="completed",
            started_at=started_at,
            completed_at=datetime.now(UTC),
            position_count=len(result.positions),
            total_equity=result.total_equity,
            decision_reports=result.decision_reports,
            notices=result.notices,
        )
    )
    return result


async def update_ai_simulation_settings(
    app: FastAPI, request: AiSimulationRunRequest
) -> AiSimulationOverview:
    """Persist account settings without running a candidate screen or trade cycle."""
    repository = ai_simulation_repository(app)
    portfolio = await repository.get_active(request.market)
    if portfolio is None:
        raise LookupError("尚未创建该市场的 AI 模拟组合")
    strategies = await _select_strategies(app, request.market, request.strategy_ids)
    _ensure_requested_strategies(request.strategy_ids, strategies)
    positions = await repository.list_open_positions(portfolio.portfolio_id)
    await _save_reconfigured_portfolio(repository, portfolio, positions, request, strategies)
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
            dict.fromkeys((*overview.notices, "AI 模拟账户设置已同步；既有持仓和交易记录已保留。"))
        ),
    )


async def ai_simulation_runs(
    app: FastAPI, market: Market, limit: int = 14
) -> list[AiSimulationRun]:
    return await ai_simulation_repository(app).list_runs(market, limit)


async def run_scheduled_ai_simulations(
    app: FastAPI,
    *,
    trading_days_only: bool = True,
    market_hours_only: bool = True,
    run_timeout_seconds: int = 480,
    observed_at: datetime | None = None,
    trading_calendar: TradingCalendarPort | None = None,
) -> None:
    """Run existing accounts only in each exchange's published trading sessions."""
    run_at = observed_at or datetime.now(UTC)
    if run_timeout_seconds <= 0:
        raise ValueError("run_timeout_seconds must be positive")
    calendar = trading_calendar or ExchangeTradingCalendar()
    repository = ai_simulation_repository(app)
    for portfolio in await repository.list_active():
        market = Market(portfolio.market)
        if trading_days_only and not calendar.is_trading_day(market, run_at):
            continue
        if market_hours_only and not calendar.is_open(market, run_at):
            continue
        started_at = datetime.now(UTC)
        try:
            await asyncio.wait_for(
                run_ai_simulation(
                    app,
                    AiSimulationRunRequest(
                        market=market,
                        initial_capital=portfolio.initial_capital,
                        max_positions=portfolio.max_positions,
                        strategy_ids=portfolio.strategy_ids,
                        trigger="scheduled",
                    ),
                ),
                timeout=run_timeout_seconds,
            )
        except TimeoutError:
            await _save_failed_scheduled_run(
                repository,
                portfolio,
                market,
                started_at,
                f"模拟任务在 {run_timeout_seconds} 秒内未完成，已停止本轮并等待下一次定时任务。",
            )
        except Exception as error:
            await _save_failed_scheduled_run(
                repository, portfolio, market, started_at, str(error)[:1_000]
            )


async def _save_failed_scheduled_run(
    repository: SqlAlchemyAiSimulationRepository,
    portfolio: AiSimulationPortfolio,
    market: Market,
    started_at: datetime,
    error_message: str,
) -> None:
    """Persist an auditable failure without blocking the next account's schedule."""
    try:
        position_count = len(await repository.list_open_positions(portfolio.portfolio_id))
        await repository.save_run(
            AiSimulationRun(
                run_id=uuid4(),
                portfolio_id=portfolio.portfolio_id,
                market=market,
                trigger="scheduled",
                status="failed",
                started_at=started_at,
                completed_at=datetime.now(UTC),
                position_count=position_count,
                total_equity=None,
                error_message=error_message,
            )
        )
    except Exception:
        # A database outage must not prevent the next account or next day from running.
        return


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
        (item for item in paper_overview.summary.currencies if item.currency == portfolio.currency),
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


async def _select_strategies(
    app: FastAPI, market: Market, strategy_ids: tuple[UUID, ...]
) -> tuple[StrategyProfile, ...]:
    if not strategy_ids:
        return ()
    available = await ListStrategiesHandler(strategy_repository(app)).handle()
    matching = {
        item.strategy_id: item
        for item in available
        if item.status == "active" and market in item.markets
    }
    return tuple(matching[strategy_id] for strategy_id in strategy_ids if strategy_id in matching)


def _ensure_requested_strategies(
    strategy_ids: tuple[UUID, ...], strategies: tuple[StrategyProfile, ...]
) -> None:
    if len(set(strategy_ids)) != len(strategy_ids):
        raise ValueError("所选策略不能重复。")
    if len(strategy_ids) != len(strategies):
        raise ValueError("所选策略不存在、未启用，或不适用于当前市场。")


def _max_position_percent(strategies: tuple[StrategyProfile, ...]) -> Decimal:
    return min((item.max_position_pct for item in strategies), default=Decimal("25"))


async def _save_reconfigured_portfolio(
    repository: SqlAlchemyAiSimulationRepository,
    portfolio: AiSimulationPortfolio,
    positions: list[AiSimulationPosition],
    request: AiSimulationRunRequest,
    strategies: tuple[StrategyProfile, ...],
) -> AiSimulationPortfolio:
    updated = reconfigure_simulation_portfolio(
        portfolio,
        initial_capital=request.initial_capital,
        max_positions=request.max_positions,
        strategy_ids=tuple(item.strategy_id for item in strategies),
        open_position_count=len(positions),
    )
    return portfolio if updated == portfolio else await repository.save_portfolio(updated)


def _candidate_from_analysis(
    candidate, analysis: dict[str, object], strategies: tuple[StrategyProfile, ...]
) -> AiSimulationCandidate:  # type: ignore[no-untyped-def]
    observations = tuple(analysis["observations"])
    requested = set().union(*(item.factor_ids for item in strategies)) if strategies else None
    relevant = tuple(
        item for item in observations if requested is None or item["identifier"] in requested
    )
    available = tuple(
        str(item["identifier"]) for item in relevant if item["direction"] != "unavailable"
    )
    unavailable = tuple(
        str(item["identifier"]) for item in relevant if item["direction"] == "unavailable"
    )
    supportive = sum(item["direction"] == "supportive" for item in relevant)
    adverse = sum(item["direction"] == "adverse" for item in relevant)
    rationale = tuple(
        str(item["interpretation"]) for item in relevant if item["direction"] == "supportive"
    ) or tuple(candidate.reasons)
    strategy_context = tuple(
        _strategy_factor_context(strategy, observations) for strategy in strategies
    )
    return AiSimulationCandidate(
        symbol=candidate.observation.instrument.symbol,
        display_name=candidate.observation.name,
        score=candidate.score,
        last_price=candidate.observation.last_price,
        supportive_factor_count=supportive,
        adverse_factor_count=adverse,
        available_factor_ids=available,
        unavailable_factor_ids=unavailable,
        rationale=tuple(dict.fromkeys((*strategy_context, *rationale))),
    )


def _strategy_factor_context(strategy: StrategyProfile, observations: tuple[object, ...]) -> str:
    relevant = [
        item
        for item in observations
        if item["identifier"] in strategy.factor_ids  # type: ignore[index]
    ]
    supportive = sum(item["direction"] == "supportive" for item in relevant)  # type: ignore[index]
    adverse = sum(item["direction"] == "adverse" for item in relevant)  # type: ignore[index]
    return f"策略「{strategy.name}」：支持 {supportive} 项，逆风 {adverse} 项。"


async def _discipline_entry_blockers(app: FastAPI, candidate) -> tuple[str, ...]:  # type: ignore[no-untyped-def]
    observation = candidate.observation
    quote = Quote(
        instrument=observation.instrument,
        last_price=observation.last_price,
        observed_at=observation.observed_at,
        source=observation.source,
    )
    decisions = await evaluate_active_disciplines(app, observation.instrument, quote)
    return disciplined_entry_blockers(decisions)


async def _apply_position_exits(
    app: FastAPI,
    repository: SqlAlchemyAiSimulationRepository,
    portfolio: AiSimulationPortfolio,
    positions: list[AiSimulationPosition],
    strategies: tuple[StrategyProfile, ...],
) -> tuple[AiSimulationPortfolio, list[AiSimulationPosition], tuple[str, ...]]:
    """Apply strict personal discipline or the default evidence-based exit policy."""
    active_positions: list[AiSimulationPosition] = []
    notices: list[str] = []
    current_portfolio = portfolio
    for position in positions:
        try:
            quote = await latest_quote(position.instrument)
        except Exception:
            active_positions.append(position)
            notices.append(
                f"{position.instrument.symbol} 未取得可验证行情，"
                "未执行任何模拟卖出；请在数据源恢复后再次复核。"
            )
            continue
        decisions = await evaluate_active_disciplines(app, position.instrument, quote)
        exit_decision = next(
            (item for item in decisions if item.status is DisciplineDecisionStatus.EXIT),
            None,
        )
        profit_decision = next(
            (item for item in decisions if item.status is DisciplineDecisionStatus.TAKE_PROFIT),
            None,
        )
        triggering_decision = exit_decision or profit_decision
        if triggering_decision is not None:
            state_label = (
                "清仓条件"
                if triggering_decision.status is DisciplineDecisionStatus.EXIT
                else "止盈条件"
            )
            decision = SimulationExitDecision(
                action="full_exit",
                quantity=position.quantity,
                reason_code="personal_discipline",
                rationale=(
                    f"个人纪律「{triggering_decision.discipline.name}」触发{state_label}，"
                    f"参考阈值 {triggering_decision.matched_level}，本轮模拟全量平仓。",
                ),
                highest_price=max(position.highest_price, quote.last_price),
                profit_take_stage=position.profit_take_stage,
                trailing_stop_price=position.trailing_stop_price,
            )
            current_portfolio, updated_position, notice = await _execute_position_sale(
                repository, current_portfolio, position, quote, decision
            )
            notices.append(notice)
            if updated_position is not None:
                active_positions.append(updated_position)
            continue

        if decisions:
            updated_position = _position_with_exit_state(
                position,
                highest_price=max(position.highest_price, quote.last_price),
                profit_take_stage=position.profit_take_stage,
                trailing_stop_price=position.trailing_stop_price,
            )
            if updated_position != position:
                updated_position = await repository.save_position(updated_position)
            if any(item.status is DisciplineDecisionStatus.ADD_CONDITION_MET for item in decisions):
                notices.append(
                    f"{position.instrument.symbol} 已满足个人纪律的加仓价；"
                    "当前版本将其保留为复核提示，不会在没有已版本化加仓计划时重复模拟买入。"
                )
            notices.append(
                f"{position.instrument.symbol} 已启用个人纪律且本轮未触发止盈/清仓；"
                "个人纪律优先，未使用默认自动卖出规则。"
            )
            active_positions.append(updated_position)
            continue

        evidence, evidence_notice = await _automatic_exit_evidence(position, quote, strategies)
        if evidence_notice is not None:
            notices.append(evidence_notice)
        decision = evaluate_simulation_exit(evidence)
        if decision.action == "hold":
            updated_position = _position_with_exit_state(
                position,
                highest_price=decision.highest_price,
                profit_take_stage=decision.profit_take_stage,
                trailing_stop_price=decision.trailing_stop_price,
            )
            if updated_position != position:
                updated_position = await repository.save_position(updated_position)
            active_positions.append(updated_position)
            continue

        current_portfolio, updated_position, notice = await _execute_position_sale(
            repository, current_portfolio, position, quote, decision
        )
        notices.append(notice)
        if updated_position is not None:
            active_positions.append(updated_position)
    return current_portfolio, active_positions, tuple(notices)


async def _automatic_exit_evidence(
    position: AiSimulationPosition,
    quote: Quote,
    strategies: tuple[StrategyProfile, ...],
) -> tuple[SimulationExitEvidence, str | None]:
    atr_14 = None
    sma_20 = None
    factor_directions: tuple[tuple[str, str], ...] = ()
    notice = None
    try:
        provider = historical_bars_provider(position.instrument)
        bars = await provider.get_daily_bars(position.instrument, limit=90)
        indicators = calculate_indicators(bars)
        analysis = analyze_builtin_factors(
            position.instrument,
            bars,
            technical_source=provider.name,
        )
        requested_factor_ids = (
            set().union(*(strategy.factor_ids for strategy in strategies))
            if strategies
            else {
                "momentum_20d",
                "volatility_20d",
                "short_reversal_5d",
                "moving_average_trend",
                "relative_volume_20d",
                "news_sentiment",
            }
        )
        factor_directions = tuple(
            (item.identifier, item.direction)
            for item in analysis.observations
            if item.identifier in requested_factor_ids and item.direction != "unavailable"
        )
        atr_14 = indicators.atr_14
        sma_20 = indicators.sma_20
    except Exception as error:
        notice = (
            f"{position.instrument.symbol} 日线/因子退出证据暂不可用：{error}；"
            "本轮仍检查硬止损、固定盈利目标和已启用的移动保护。"
        )
    return (
        SimulationExitEvidence(
            current_price=quote.last_price,
            average_cost=position.average_cost,
            quantity=position.quantity,
            highest_price=position.highest_price,
            profit_take_stage=position.profit_take_stage,
            lot_size=minimum_trade_unit(position.instrument),
            atr_14=atr_14,
            sma_20=sma_20,
            factor_directions=factor_directions,
        ),
        notice,
    )


async def _execute_position_sale(
    repository: SqlAlchemyAiSimulationRepository,
    portfolio: AiSimulationPortfolio,
    position: AiSimulationPosition,
    quote: Quote,
    decision: SimulationExitDecision,
) -> tuple[AiSimulationPortfolio, AiSimulationPosition | None, str]:
    execution = estimate_simulated_execution(
        side="sell", reference_price=quote.last_price, quantity=decision.quantity
    )
    rationale = (
        *decision.rationale,
        *(
            ()
            if decision.reason_code == "personal_discipline"
            else (f"自动退出规则版本：{EXIT_POLICY_VERSION}。",)
        ),
        f"行情来源：{quote.source}，观测时间：{quote.observed_at.isoformat()}。",
        *execution.rationale,
    )
    remaining_quantity = position.quantity - decision.quantity
    is_closed = decision.action == "full_exit" or remaining_quantity <= 0
    updated_position = AiSimulationPosition(
        position_id=position.position_id,
        portfolio_id=position.portfolio_id,
        instrument=position.instrument,
        quantity=position.quantity if is_closed else remaining_quantity,
        average_cost=position.average_cost,
        opened_at=position.opened_at,
        candidate_score=position.candidate_score,
        factor_context=position.factor_context,
        rationale=tuple((*position.rationale, *rationale)),
        highest_price=decision.highest_price,
        profit_take_stage=decision.profit_take_stage,
        trailing_stop_price=decision.trailing_stop_price,
        status="closed" if is_closed else "open",
    )
    updated_position = await repository.save_position(updated_position)
    await repository.save_trade(
        AiSimulationTrade(
            trade_id=uuid4(),
            portfolio_id=portfolio.portfolio_id,
            position_id=position.position_id,
            side="sell",
            quantity=decision.quantity,
            price=execution.fill_price,
            executed_at=datetime.now(UTC),
            rationale=rationale,
        )
    )
    updated_portfolio = AiSimulationPortfolio(
        portfolio_id=portfolio.portfolio_id,
        market=portfolio.market,
        currency=portfolio.currency,
        initial_capital=portfolio.initial_capital,
        cash_balance=portfolio.cash_balance + execution.cash_proceeds,
        max_positions=portfolio.max_positions,
        strategy_ids=portfolio.strategy_ids,
        status=portfolio.status,
    )
    updated_portfolio = await repository.save_portfolio(updated_portfolio)
    action_label = "全量平仓" if is_closed else f"分批卖出 {decision.quantity}"
    notice = (
        f"{position.instrument.symbol} 已因「{_exit_reason_label(decision.reason_code)}」"
        f"完成{action_label}；仅更新模拟账户，不会提交真实订单。"
    )
    return updated_portfolio, None if is_closed else updated_position, notice


def _position_with_exit_state(
    position: AiSimulationPosition,
    *,
    highest_price: Decimal,
    profit_take_stage: int,
    trailing_stop_price: Decimal | None,
) -> AiSimulationPosition:
    return AiSimulationPosition(
        position_id=position.position_id,
        portfolio_id=position.portfolio_id,
        instrument=position.instrument,
        quantity=position.quantity,
        average_cost=position.average_cost,
        opened_at=position.opened_at,
        candidate_score=position.candidate_score,
        factor_context=position.factor_context,
        rationale=position.rationale,
        highest_price=highest_price,
        profit_take_stage=profit_take_stage,
        trailing_stop_price=trailing_stop_price,
        status=position.status,
    )


def _exit_reason_label(reason_code: str) -> str:
    return {
        "personal_discipline": "个人纪律",
        "hard_stop_loss": "8% 硬止损",
        "first_profit_target": "20% 首次盈利目标",
        "trailing_profit_stop": "ATR 移动盈利保护",
        "confirmed_trend_breakdown": "均线与多因子趋势转弱",
    }.get(reason_code, reason_code)


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
