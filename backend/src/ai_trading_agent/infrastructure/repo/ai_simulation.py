"""Private PostgreSQL repository for auditable AI paper-trading state."""

from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from ai_trading_agent.domain.aggregate.ai_simulation import (
    AiSimulationPortfolio,
    AiSimulationPosition,
    AiSimulationRun,
    AiSimulationTrade,
)
from ai_trading_agent.domain.aggregate.market import Instrument
from ai_trading_agent.domain.enums.market import InstrumentType, Market
from ai_trading_agent.infrastructure.repo.models import (
    AiSimulationPortfolioRecord,
    AiSimulationPositionRecord,
    AiSimulationRunRecord,
    AiSimulationTradeRecord,
)


class SqlAlchemyAiSimulationRepository:
    def __init__(self, sessions: async_sessionmaker[AsyncSession]) -> None:
        self._sessions = sessions

    async def get_active(self, market: Market) -> AiSimulationPortfolio | None:
        async with self._sessions() as session:
            record = await session.scalar(
                select(AiSimulationPortfolioRecord)
                .where(
                    AiSimulationPortfolioRecord.market == market.value,
                    AiSimulationPortfolioRecord.status == "active",
                )
                .order_by(AiSimulationPortfolioRecord.updated_at.desc())
                .limit(1)
            )
            return None if record is None else _portfolio(record)

    async def list_active(self) -> list[AiSimulationPortfolio]:
        async with self._sessions() as session:
            records = (
                await session.scalars(
                    select(AiSimulationPortfolioRecord)
                    .where(AiSimulationPortfolioRecord.status == "active")
                    .order_by(AiSimulationPortfolioRecord.updated_at.desc())
                )
            ).all()
            return [_portfolio(record) for record in records]

    async def save_portfolio(self, portfolio: AiSimulationPortfolio) -> AiSimulationPortfolio:
        async with self._sessions() as session:
            record = await session.get(AiSimulationPortfolioRecord, str(portfolio.portfolio_id))
            if record is None:
                record = AiSimulationPortfolioRecord(portfolio_id=str(portfolio.portfolio_id))
                session.add(record)
            record.market = portfolio.market
            record.currency = portfolio.currency
            record.initial_capital = portfolio.initial_capital
            record.cash_balance = portfolio.cash_balance
            record.max_positions = portfolio.max_positions
            record.strategy_id = (
                None if portfolio.strategy_id is None else str(portfolio.strategy_id)
            )
            record.status = portfolio.status
            await session.commit()
            await session.refresh(record)
            return _portfolio(record)

    async def list_open_positions(self, portfolio_id: UUID) -> list[AiSimulationPosition]:
        async with self._sessions() as session:
            records = (
                await session.scalars(
                    select(AiSimulationPositionRecord)
                    .where(
                        AiSimulationPositionRecord.portfolio_id == str(portfolio_id),
                        AiSimulationPositionRecord.status == "open",
                    )
                    .order_by(AiSimulationPositionRecord.opened_at.desc())
                )
            ).all()
            return [_position(record) for record in records]

    async def save_position(self, position: AiSimulationPosition) -> AiSimulationPosition:
        async with self._sessions() as session:
            record = AiSimulationPositionRecord(
                position_id=str(position.position_id),
                portfolio_id=str(position.portfolio_id),
                symbol=position.instrument.symbol,
                market=position.instrument.market.value,
                instrument_type=position.instrument.instrument_type.value,
                quantity=position.quantity,
                average_cost=position.average_cost,
                opened_at=position.opened_at,
                candidate_score=position.candidate_score,
                factor_context=list(position.factor_context),
                rationale=list(position.rationale),
                status=position.status,
            )
            session.add(record)
            await session.commit()
            await session.refresh(record)
            return _position(record)

    async def save_trade(self, trade: AiSimulationTrade) -> AiSimulationTrade:
        async with self._sessions() as session:
            record = AiSimulationTradeRecord(
                trade_id=str(trade.trade_id),
                portfolio_id=str(trade.portfolio_id),
                position_id=None if trade.position_id is None else str(trade.position_id),
                side=trade.side,
                quantity=trade.quantity,
                price=trade.price,
                executed_at=trade.executed_at,
                rationale=list(trade.rationale),
            )
            session.add(record)
            await session.commit()
            await session.refresh(record)
            return _trade(record)

    async def save_run(self, run: AiSimulationRun) -> AiSimulationRun:
        async with self._sessions() as session:
            record = AiSimulationRunRecord(
                run_id=str(run.run_id),
                portfolio_id=str(run.portfolio_id),
                market=run.market.value,
                trigger=run.trigger,
                status=run.status,
                started_at=run.started_at,
                completed_at=run.completed_at,
                position_count=run.position_count,
                total_equity=run.total_equity,
                decision_reports=[
                    {
                        "symbol": item.symbol,
                        "display_name": item.display_name,
                        "score": str(item.score),
                        "decision": item.decision,
                        "supportive_factor_count": item.supportive_factor_count,
                        "adverse_factor_count": item.adverse_factor_count,
                        "available_factor_ids": list(item.available_factor_ids),
                        "unavailable_factor_ids": list(item.unavailable_factor_ids),
                        "blockers": list(item.blockers),
                    }
                    for item in run.decision_reports
                ],
                notices=list(run.notices),
                error_message=run.error_message,
            )
            session.add(record)
            await session.commit()
            await session.refresh(record)
            return _run(record)

    async def list_runs(self, market: Market, limit: int) -> list[AiSimulationRun]:
        async with self._sessions() as session:
            records = (
                await session.scalars(
                    select(AiSimulationRunRecord)
                    .where(AiSimulationRunRecord.market == market.value)
                    .order_by(AiSimulationRunRecord.completed_at.desc())
                    .limit(limit)
                )
            ).all()
            return [_run(record) for record in records]


def _portfolio(record: AiSimulationPortfolioRecord) -> AiSimulationPortfolio:
    return AiSimulationPortfolio(
        portfolio_id=UUID(record.portfolio_id),
        market=record.market,
        currency=record.currency,
        initial_capital=Decimal(str(record.initial_capital)),
        cash_balance=Decimal(str(record.cash_balance)),
        max_positions=record.max_positions,
        strategy_id=None if record.strategy_id is None else UUID(record.strategy_id),
        status=record.status,
    )


def _position(record: AiSimulationPositionRecord) -> AiSimulationPosition:
    return AiSimulationPosition(
        position_id=UUID(record.position_id),
        portfolio_id=UUID(record.portfolio_id),
        instrument=Instrument(
            record.symbol,
            Market(record.market),
            InstrumentType(record.instrument_type),
        ),
        quantity=Decimal(str(record.quantity)),
        average_cost=Decimal(str(record.average_cost)),
        opened_at=record.opened_at,
        candidate_score=Decimal(str(record.candidate_score)),
        factor_context=tuple(str(item) for item in record.factor_context),
        rationale=tuple(str(item) for item in record.rationale),
        status=record.status,
    )


def _trade(record: AiSimulationTradeRecord) -> AiSimulationTrade:
    return AiSimulationTrade(
        trade_id=UUID(record.trade_id),
        portfolio_id=UUID(record.portfolio_id),
        position_id=None if record.position_id is None else UUID(record.position_id),
        side=record.side,
        quantity=Decimal(str(record.quantity)),
        price=Decimal(str(record.price)),
        executed_at=record.executed_at,
        rationale=tuple(str(item) for item in record.rationale),
    )


def _run(record: AiSimulationRunRecord) -> AiSimulationRun:
    from ai_trading_agent.domain.aggregate.ai_simulation import AiSimulationDecisionReport

    return AiSimulationRun(
        run_id=UUID(record.run_id),
        portfolio_id=UUID(record.portfolio_id),
        market=Market(record.market),
        trigger=record.trigger,
        status=record.status,
        started_at=record.started_at,
        completed_at=record.completed_at,
        position_count=record.position_count,
        total_equity=None if record.total_equity is None else Decimal(str(record.total_equity)),
        decision_reports=tuple(
            AiSimulationDecisionReport(
                symbol=str(item["symbol"]),
                display_name=None
                if item.get("display_name") is None
                else str(item["display_name"]),
                score=Decimal(str(item["score"])),
                decision=str(item["decision"]),
                supportive_factor_count=int(item["supportive_factor_count"]),
                adverse_factor_count=int(item["adverse_factor_count"]),
                available_factor_ids=tuple(str(value) for value in item["available_factor_ids"]),
                unavailable_factor_ids=tuple(
                    str(value) for value in item["unavailable_factor_ids"]
                ),
                blockers=tuple(str(value) for value in item["blockers"]),
            )
            for item in record.decision_reports
        ),
        notices=tuple(str(item) for item in record.notices),
        error_message=record.error_message,
    )
