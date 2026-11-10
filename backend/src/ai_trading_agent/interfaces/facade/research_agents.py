"""Composition root binding adaptive research to existing read-only data services."""

import asyncio
import json
from dataclasses import asdict, replace
from datetime import UTC, datetime
from decimal import Decimal

from ai_trading_agent.application.research_agent import (
    ResearchAgent,
    AgentLimits,
    AgentResult,
    optional_position_review,
)
from ai_trading_agent.domain.service.agent_evidence import validate_agent_report
from ai_trading_agent.domain.service.agent_review import (
    ResearchPolicy,
    review_entry,
    position_advice_eligible,
)
from ai_trading_agent.infrastructure.config.news import OpenAICompatibleLLMSettings
from ai_trading_agent.infrastructure.repo.agent import AgentRepository
from ai_trading_agent.infrastructure.rpc.research_agent import CompatibleResearchModel
from ai_trading_agent.infrastructure.rpc.llm_usage import usage_feature
from ai_trading_agent.interfaces.facade.persistence import private_session_factory
from ai_trading_agent.interfaces.model.agent import AgentSettings


def repository(app):
    return AgentRepository(private_session_factory(app))


async def settings(app, account):
    generation, raw = await repository(app).config(account)
    return generation, AgentSettings.model_validate(raw)


async def run_research(app, account, instrument, strategies, *, kind, position=None):
    repo = repository(app)
    generation, config = await settings(app, account.portfolio_id)
    if kind == "position" and not config.position_enabled:
        return None
    await repo.ensure(account.portfolio_id)
    generation, config = await settings(app, account.portfolio_id)
    if kind == "position" and not config.position_enabled:
        return None
    started = datetime.now(UTC)
    initial = (
        await repo.history(account.portfolio_id, position.position_id, limit=1) if position else []
    )
    context = {
        "kind": kind,
        "symbol": instrument.symbol,
        "market": instrument.market.value,
        "holding_days": config.holding_days,
        "cash": str(account.cash_balance),
        "strategies": [
            {"name": s.name, "thesis": s.thesis, "risk_notes": s.risk_notes} for s in strategies
        ],
        "original_thesis": initial[0].get("report") if initial else None,
    }
    from ai_trading_agent.interfaces.facade.disciplines import get_discipline

    discipline_rules = [
        await get_discipline(app, identifier) for identifier in account.discipline_ids
    ]
    context["personal_disciplines"] = [rule.definition() for rule in discipline_rules if rule]
    if position:
        context["position"] = {
            "cost": str(position.average_cost),
            "quantity": str(position.quantity),
            "opened_at": position.opened_at.isoformat(),
        }
    cache = {}

    async def tool(name, arguments):
        if arguments:
            raise ValueError("tools are bound to this instrument; no arbitrary parameters")
        from ai_trading_agent.interfaces.facade.research_workspace import (
            latest_quote,
            research,
            technical_study,
            watchlist_financial_detail,
        )
        from ai_trading_agent.interfaces.model.http import ResearchRequest, TechnicalRequest

        if name == "quote":
            value = asdict(await latest_quote(instrument))
        elif name == "technical":
            study = await technical_study(
                TechnicalRequest(
                    symbol=instrument.symbol,
                    market=instrument.market,
                    instrument_type=instrument.instrument_type,
                )
            )
            value = {"assessment": study.assessment, "indicators": study.indicators}
        else:
            if "research" not in cache:
                cache["research"] = await research(
                    ResearchRequest(
                        symbol=instrument.symbol,
                        market=instrument.market,
                        instrument_type=instrument.instrument_type,
                    )
                )
            report = cache["research"]
            field = {
                "financials": "fundamentals",
                "capital_flow": "capital_flow",
                "factors": "factor_analysis",
                "news": "news_sentiment",
            }[name]
            value = getattr(report, field)
            if not value:
                raise ValueError("data unavailable")
            if (
                name == "financials"
                and instrument.market.value == "a_share"
                and instrument.instrument_type.value == "equity"
            ):
                detail = await watchlist_financial_detail(instrument)
                value = {"statements": asdict(detail), "summary": value}
            if name == "news":
                value = {
                    "source": value.get("source"),
                    "direct": (value.get("instrument") or {}).get("evidence", []),
                    "industry": (value.get("industry") or {}).get("evidence", [])[:1],
                    "limitations": value.get("limitations", []),
                }
                if report.fund_research:
                    value["direct"] = report.fund_research.get("news", [])[:4]
                if not value["direct"] and not value["industry"]:
                    raise ValueError("no news evidence available")
        return {
            "source": "existing_provider:" + name,
            "retrieved_at": datetime.now(UTC).isoformat(),
            "data": json.dumps(value, ensure_ascii=False, default=str)[:2200],
            "note": "可能截断；来源日期以data原始披露/行情日期为准，retrieved_at不是事件发生时间",
        }

    names = ("quote", "news", "financials", "capital_flow", "factors", "technical")
    tools = {name: (lambda arguments, name=name: tool(name, arguments)) for name in names}

    async def permitted():
        new_generation, current = await settings(app, account.portfolio_id)
        return new_generation == generation and (kind == "buy" or current.position_enabled)

    from ai_trading_agent.interfaces.facade.news_research import skip_news_model

    result = AgentResult("running")
    payload = {
        **asdict(result),
        "generation": generation,
        "settings": config.model_dump(mode="json"),
        "context": context,
        "started_at": started.isoformat(),
        "rule_review": {"action": "pending"},
    }
    audit_id = await repo.audit(
        account.portfolio_id,
        instrument.symbol,
        kind,
        payload,
        position.position_id if position else None,
    )
    cancelled = False
    token = skip_news_model.set(True)
    feature = usage_feature.set("buy_research_agent" if kind == "buy" else "position_review_agent")
    try:
        if position and not initial:
            result = AgentResult("insufficient_evidence")
        else:
            agent = ResearchAgent(
                CompatibleResearchModel(OpenAICompatibleLLMSettings.from_environment()),
                tools,
                validate_report=validate_agent_report,
                limits=AgentLimits(
                    config.rounds, config.tokens, config.timeout_seconds, config.repeated_queries
                ),
            )
            if kind == "position":

                async def current_generation():
                    version, current = await settings(app, account.portfolio_id)
                    return version if current.position_enabled else None

                result = await optional_position_review(
                    agent, context, current_generation=current_generation
                )
            else:
                result = await agent.run(context, permitted=permitted, result=result)
    except asyncio.CancelledError:
        cancelled = True
        result.status, result.report = "cancelled", None
    except Exception:
        result = AgentResult("failed")
    finally:
        skip_news_model.reset(token)
        usage_feature.reset(feature)
    if not cancelled and not await permitted():
        result.status, result.report = "disabled", None
    payload = {
        **asdict(result),
        "generation": generation,
        "settings": config.model_dump(mode="json"),
        "context": context,
        "started_at": started.isoformat(),
        "rule_review": {"action": "pending"},
    }
    await repo.save_result(audit_id, payload)
    if cancelled:
        raise asyncio.CancelledError
    return audit_id, payload, config


async def buy_review(app, candidate, portfolio, strategies, count, simulated, old_decision):
    from ai_trading_agent.interfaces.facade.ai_simulation import (
        _discipline_entry_blockers,
        _max_position_percent,
        minimum_trade_unit,
    )
    from ai_trading_agent.interfaces.facade.research_workspace import latest_quote
    from ai_trading_agent.domain.service.ai_simulation import (
        evaluate_simulated_entry,
        AiSimulationEntryDecision,
    )

    audit_id, payload, config = await run_research(
        app, portfolio, candidate.observation.instrument, strategies, kind="buy"
    )
    report = payload.get("report") or {}
    policy = ResearchPolicy(
        config.workflow_weight,
        config.research_weight,
        config.entry_threshold,
        config.validity_seconds,
        config.max_price_move,
    )
    blockers = list(old_decision.blockers)
    if report.get("recommendation") != "buy":
        blockers.append("研究 Agent 未建议买入")
    blockers.extend(
        "研究风险暂缓：" + risk["text"]
        for risk in report.get("risks", [])
        if risk["severity"] in {"major", "critical"}
    )
    fresh = None
    try:
        fresh = await latest_quote(candidate.observation.instrument)
        blockers.extend(
            policy.quote_blockers(
                reference=candidate.observation.last_price,
                current=fresh.last_price,
                researched_at=datetime.fromisoformat(payload["started_at"]),
                quoted_at=fresh.observed_at,
                now=datetime.now(UTC),
            )
        )
        if report and not Decimal(report["price_min"]) <= fresh.last_price <= Decimal(
            report["price_max"]
        ):
            blockers.append("最新报价超出 Agent 研究价格区间")
        refreshed = replace(
            candidate,
            observation=replace(
                candidate.observation,
                last_price=fresh.last_price,
                observed_at=fresh.observed_at,
                source=fresh.source,
            ),
        )
        blockers.extend(await _discipline_entry_blockers(app, refreshed, portfolio.discipline_ids))
    except Exception:
        blockers.append("研究后未取得可验证新报价")
    generation, _ = await settings(app, portfolio.portfolio_id)
    if generation != payload["generation"]:
        blockers.append("研究期间账户研究配置已变化")
    score, reviewed = review_entry(
        policy,
        status=payload["status"],
        workflow_score=candidate.score,
        research_score=Decimal(report["score"]) if report else None,
        hard_blockers=tuple(blockers),
    )
    simulated = replace(
        simulated,
        score=score if score is not None else simulated.score,
        last_price=fresh.last_price if fresh else simulated.last_price,
        rationale=(
            *simulated.rationale,
            f"买入研究：{payload['status']}；基础分 {candidate.score}；研究分 {report.get('score', '不可用')}；综合分 {score if score is not None else '不可用'}",
            f"研究审计：{audit_id}",
        ),
    )
    decision = evaluate_simulated_entry(
        simulated,
        available_cash=portfolio.cash_balance,
        initial_capital=portfolio.initial_capital,
        open_position_count=count,
        max_positions=portfolio.max_positions,
        max_position_percent=_max_position_percent(strategies),
        lot_size=minimum_trade_unit(candidate.observation.instrument),
        minimum_score=config.entry_threshold,
    )
    if reviewed:
        decision = AiSimulationEntryDecision(
            None, tuple(dict.fromkeys((*reviewed, *decision.blockers)))
        )
    await repository(app).finish(
        audit_id,
        {
            "action": "approved" if decision.allocation else "skip",
            "blockers": list(decision.blockers),
            "workflow_score": str(candidate.score),
            "research_score": report.get("score"),
            "combined_score": str(score) if score is not None else None,
            "quote": {
                "price": str(fresh.last_price),
                "observed_at": fresh.observed_at.isoformat(),
                "source": fresh.source,
            }
            if fresh
            else None,
        },
    )
    return simulated, decision


def audit_identifier(simulated):
    return next(
        (s.split("：", 1)[1] for s in simulated.rationale if s.startswith("研究审计：")), None
    )


async def review_positions(app, trading_repo, portfolio, positions, strategies):
    """Optional work runs after all baseline exits, never replaces hard protections."""
    try:
        _, current = await settings(app, portfolio.portfolio_id)
    except Exception:
        return portfolio, positions, ("持仓 Agent 配置暂不可用，已执行原有持仓规则。",)
    if not current.position_enabled:
        return portfolio, positions, ()
    from zoneinfo import ZoneInfo
    from ai_trading_agent.domain.enums.market import Market
    from ai_trading_agent.domain.service.simulation_exit import SimulationExitDecision
    from ai_trading_agent.domain.service.simulated_execution import quantity_for_partial_exit
    from ai_trading_agent.interfaces.facade.ai_simulation import (
        _execute_position_sale,
        minimum_trade_unit,
    )
    from ai_trading_agent.interfaces.facade.disciplines import evaluate_active_disciplines
    from ai_trading_agent.interfaces.facade.research_workspace import latest_quote

    remaining, notes = [], []
    for position in positions:
        try:
            response = await run_research(
                app, portfolio, position.instrument, strategies, kind="position", position=position
            )
        except Exception:
            remaining.append(position)
            notes.append(f"{position.instrument.symbol} 持仓研究失败，保留原有持仓规则结果。")
            continue
        if response is None:
            remaining.append(position)
            continue
        audit_id, payload, config = response
        report = payload.get("report") or {}
        outcome = {"action": "hold", "blockers": []}
        action = report.get("recommendation")
        eligible = position_advice_eligible(payload["status"], report)
        if not eligible:
            outcome["blockers"].append("持仓研究未形成附证据的假设削弱/失效建议；保留原规则结果")
        else:
            try:
                quote = await latest_quote(position.instrument)
                policy = ResearchPolicy(
                    config.workflow_weight,
                    config.research_weight,
                    config.entry_threshold,
                    config.validity_seconds,
                    config.max_price_move,
                )
                outcome["blockers"].extend(
                    policy.quote_blockers(
                        reference=quote.last_price,
                        current=quote.last_price,
                        researched_at=datetime.fromisoformat(payload["started_at"]),
                        quoted_at=quote.observed_at,
                        now=datetime.now(UTC),
                    )
                )
                if (
                    position.instrument.market is Market.A_SHARE
                    and position.opened_at.astimezone(ZoneInfo("Asia/Shanghai")).date()
                    >= quote.observed_at.astimezone(ZoneInfo("Asia/Shanghai")).date()
                ):
                    outcome["blockers"].append("T+1 结算约束")
                if await evaluate_active_disciplines(
                    app, position.instrument, quote, portfolio.discipline_ids
                ):
                    outcome["blockers"].append("个人纪律优先，Agent 不替代纪律卖出条件")
                async with repository(app).guard(portfolio.portfolio_id) as (session, row):
                    outcome["blockers"].extend(
                        policy.quote_blockers(
                            reference=quote.last_price,
                            current=quote.last_price,
                            researched_at=datetime.fromisoformat(payload["started_at"]),
                            quoted_at=quote.observed_at,
                            now=datetime.now(UTC),
                        )
                    )
                    if (
                        row is None
                        or row.generation != payload["generation"]
                        or not AgentSettings.model_validate(row.settings).position_enabled
                    ):
                        outcome["blockers"].append("持仓 Agent 已关闭或配置版本已变化")
                    live = await trading_repo.get(portfolio.portfolio_id)
                    live_positions = await trading_repo.list_open_positions(portfolio.portfolio_id)
                    same = next(
                        (p for p in live_positions if p.position_id == position.position_id), None
                    )
                    if (
                        live is None
                        or live.status != "active"
                        or same is None
                        or same.quantity != position.quantity
                    ):
                        outcome["blockers"].append("账户或持仓状态已变化")
                    if not outcome["blockers"]:
                        quantity = (
                            position.quantity
                            if action == "exit"
                            else quantity_for_partial_exit(
                                position.quantity, minimum_trade_unit(position.instrument)
                            )
                        )
                        decision = SimulationExitDecision(
                            "full_exit" if quantity == position.quantity else "partial_exit",
                            quantity,
                            "agent_thesis_review",
                            ("持仓假设复核：" + report["thesis"]["text"], f"研究审计：{audit_id}"),
                            max(position.highest_price, quote.last_price),
                            position.profit_take_stage,
                            position.trailing_stop_price,
                        )
                        from ai_trading_agent.infrastructure.repo.ai_simulation import (
                            SqlAlchemyAiSimulationRepository,
                        )
                        from ai_trading_agent.infrastructure.repo.models import AgentAuditRecord

                        portfolio, updated, note = await _execute_position_sale(
                            SqlAlchemyAiSimulationRepository.within_transaction(session),
                            portfolio,
                            position,
                            quote,
                            decision,
                        )
                        outcome.update(
                            action=decision.action,
                            quantity=str(quantity),
                            reference_price=str(quote.last_price),
                        )
                        notes.append(note)
                        record = await session.get(AgentAuditRecord, audit_id)
                        record.payload = {**record.payload, "rule_review": outcome}
                        if updated:
                            remaining.append(updated)
                        continue
            except Exception:
                outcome["blockers"].append("持仓建议无法完成规则复核，保留原规则结果")
        remaining.append(position)
        notes.append(
            f"{position.instrument.symbol} 持仓 Agent：{payload['status']}；"
            + "；".join(outcome["blockers"])
        )
        await repository(app).finish(audit_id, outcome)
    return portfolio, remaining, tuple(notes)


async def execute_buy(app, candidate, portfolio, strategies, simulated):
    from uuid import uuid4
    from sqlalchemy import select
    from ai_trading_agent.infrastructure.repo.models import (
        AgentAuditRecord,
        AiSimulationPortfolioRecord,
    )
    from ai_trading_agent.infrastructure.repo.ai_simulation import SqlAlchemyAiSimulationRepository
    from ai_trading_agent.interfaces.facade.ai_simulation import (
        _discipline_entry_blockers,
        _max_position_percent,
        minimum_trade_unit,
    )
    from ai_trading_agent.interfaces.facade.research_workspace import latest_quote
    from ai_trading_agent.domain.service.ai_simulation import evaluate_simulated_entry
    from ai_trading_agent.domain.service.simulated_execution import estimate_simulated_execution
    from ai_trading_agent.domain.service.simulation_exit import (
        SimulationExitEvidence,
        review_exit_plan,
    )
    from ai_trading_agent.domain.aggregate.ai_simulation import (
        AiSimulationPosition,
        AiSimulationTrade,
    )

    identifier = audit_identifier(simulated)
    if not identifier:
        return portfolio, None, ("缺少持久化买入研究",)
    try:
        quote = await latest_quote(candidate.observation.instrument)
        refreshed = replace(
            candidate,
            observation=replace(
                candidate.observation,
                last_price=quote.last_price,
                observed_at=quote.observed_at,
                source=quote.source,
            ),
        )
        blockers = list(await _discipline_entry_blockers(app, refreshed, portfolio.discipline_ids))
    except Exception:
        await repository(app).finish(
            identifier, {"action": "skip", "blockers": ["成交前报价复核失败"]}
        )
        return portfolio, None, ("成交前报价复核失败",)
    async with repository(app).guard(portfolio.portfolio_id) as (session, config_row):
        record = await session.get(AgentAuditRecord, identifier)
        payload = record.payload
        config = AgentSettings.model_validate(config_row.settings)
        if config_row.generation != payload["generation"]:
            blockers.append("研究配置版本已变化，旧研究不再执行")
        await session.scalar(
            select(AiSimulationPortfolioRecord)
            .where(AiSimulationPortfolioRecord.portfolio_id == str(portfolio.portfolio_id))
            .with_for_update()
        )
        repo = SqlAlchemyAiSimulationRepository.within_transaction(session)
        live = await repo.get(portfolio.portfolio_id)
        positions = await repo.list_open_positions(portfolio.portfolio_id)
        if (
            live.status != "active"
            or live.strategy_ids != portfolio.strategy_ids
            or live.discipline_ids != portfolio.discipline_ids
        ):
            blockers.append("账户状态或策略纪律已变化")
        if any(p.instrument == candidate.observation.instrument for p in positions):
            blockers.append("已有相同标的仓位")
        policy = ResearchPolicy(
            config.workflow_weight,
            config.research_weight,
            config.entry_threshold,
            config.validity_seconds,
            config.max_price_move,
        )
        blockers.extend(
            policy.quote_blockers(
                reference=candidate.observation.last_price,
                current=quote.last_price,
                researched_at=datetime.fromisoformat(payload["started_at"]),
                quoted_at=quote.observed_at,
                now=datetime.now(UTC),
            )
        )
        report = payload["report"]
        if report and (
            report.get("recommendation") != "buy"
            or any(r["severity"] in {"major", "critical"} for r in report.get("risks", []))
        ):
            blockers.append("研究建议或重大风险不允许买入")
        if (
            not report
            or payload["status"] != "completed"
            or not Decimal(report["price_min"]) <= quote.last_price <= Decimal(report["price_max"])
        ):
            blockers.append("研究状态或成交价格区间不满足")
        decision = evaluate_simulated_entry(
            replace(simulated, last_price=quote.last_price),
            available_cash=live.cash_balance,
            initial_capital=live.initial_capital,
            open_position_count=len(positions),
            max_positions=live.max_positions,
            max_position_percent=_max_position_percent(strategies),
            lot_size=minimum_trade_unit(candidate.observation.instrument),
            minimum_score=config.entry_threshold,
        )
        blockers.extend(decision.blockers)
        if blockers or decision.allocation is None:
            record.payload = {
                **payload,
                "rule_review": {
                    **payload.get("rule_review", {}),
                    "action": "skip",
                    "blockers": blockers,
                },
            }
            return live, None, tuple(blockers)
        execution = estimate_simulated_execution(
            side="buy", reference_price=quote.last_price, quantity=decision.allocation.quantity
        )
        now = datetime.now(UTC)
        position = AiSimulationPosition(
            uuid4(),
            live.portfolio_id,
            candidate.observation.instrument,
            decision.allocation.quantity,
            execution.cash_required / decision.allocation.quantity,
            now,
            simulated.score,
            simulated.available_factor_ids or ("因子缺失",),
            (*decision.allocation.rationale, *execution.rationale),
            execution.fill_price,
        )
        evidence = SimulationExitEvidence(
            quote.last_price,
            position.average_cost,
            position.quantity,
            position.highest_price,
            0,
            minimum_trade_unit(position.instrument),
        )
        position = replace(
            position,
            exit_plan=review_exit_plan(
                evidence,
                None,
                now,
                data_notes=("建仓先设基础价格保护；下轮独立持仓规则按 ATR、资金与因子更新。",),
            ),
        )
        await repo.save_position(position)
        await repo.save_trade(
            AiSimulationTrade(
                uuid4(),
                live.portfolio_id,
                position.position_id,
                "buy",
                position.quantity,
                execution.fill_price,
                now,
                position.rationale,
            )
        )
        live = await repo.save_portfolio(
            replace(live, cash_balance=live.cash_balance - execution.cash_required)
        )
        record.position_id = str(position.position_id)
        record.payload = {
            **payload,
            "rule_review": {
                **payload.get("rule_review", {}),
                "action": "buy",
                "quantity": str(position.quantity),
                "fill_price": str(execution.fill_price),
                "quote_source": quote.source,
                "quote_at": quote.observed_at.isoformat(),
            },
        }
        return live, position, ()
