"""SQLAlchemy records for auditable, private-server PostgreSQL storage."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import JSON, Date, DateTime, ForeignKey, Index, Integer, Numeric, String, Text, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

SCHEMA = "trading_agent"


class Base(DeclarativeBase):
    pass


class TimestampedRecord:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class FactorDefinitionRecord(Base, TimestampedRecord):
    __tablename__ = "factor_definitions"
    __table_args__ = {"schema": SCHEMA}

    identifier: Mapped[str] = mapped_column(String(64), primary_key=True)
    version: Mapped[str] = mapped_column(String(32), primary_key=True)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    theme: Mapped[str] = mapped_column(String(64), nullable=False)
    formula: Mapped[str] = mapped_column(Text, nullable=False)
    columns_required: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    warmup_bars: Mapped[int] = mapped_column(Integer, nullable=False)
    horizon_days: Mapped[int] = mapped_column(Integer, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)


class StrategyProfileRecord(Base, TimestampedRecord):
    __tablename__ = "strategy_profiles"
    __table_args__ = {"schema": SCHEMA}

    strategy_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="draft")
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    definition: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)


class TradingDisciplineRecord(Base, TimestampedRecord):
    __tablename__ = "trading_disciplines"
    __table_args__ = {"schema": SCHEMA}

    discipline_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    symbol: Mapped[str] = mapped_column(String(64), nullable=False)
    market: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="active")
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    definition: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)


class WatchlistItemRecord(Base, TimestampedRecord):
    __tablename__ = "watchlist_items"
    __table_args__ = {"schema": SCHEMA}

    item_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    symbol: Mapped[str] = mapped_column(String(64), nullable=False)
    market: Mapped[str] = mapped_column(String(32), nullable=False)
    instrument_type: Mapped[str] = mapped_column(String(32), nullable=False)
    label: Mapped[str] = mapped_column(String(160), nullable=False, default="")
    notes: Mapped[str] = mapped_column(Text, nullable=False, default="")


class WatchlistAnalysisSnapshotRecord(Base, TimestampedRecord):
    __tablename__ = "watchlist_analysis_snapshots"
    __table_args__ = (
        Index("ix_watchlist_analysis_snapshots_item_observed", "watchlist_item_id", "observed_at"),
        Index("ix_watchlist_analysis_snapshots_observed_at", "observed_at"),
        {"schema": SCHEMA},
    )

    analysis_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    watchlist_item_id: Mapped[str] = mapped_column(
        ForeignKey(f"{SCHEMA}.watchlist_items.item_id", ondelete="CASCADE"), nullable=False
    )
    symbol: Mapped[str] = mapped_column(String(64), nullable=False)
    market: Mapped[str] = mapped_column(String(32), nullable=False)
    instrument_type: Mapped[str] = mapped_column(String(32), nullable=False)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    tags: Mapped[list[dict[str, str]]] = mapped_column(JSON, nullable=False, default=list)
    ai_summary: Mapped[str | None] = mapped_column(Text)
    notices: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)


class PaperPositionRecord(Base, TimestampedRecord):
    __tablename__ = "paper_positions"
    __table_args__ = {"schema": SCHEMA}

    position_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    symbol: Mapped[str] = mapped_column(String(64), nullable=False)
    market: Mapped[str] = mapped_column(String(32), nullable=False)
    instrument_type: Mapped[str] = mapped_column(String(32), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(28, 8), nullable=False)
    average_cost: Mapped[Decimal] = mapped_column(Numeric(24, 8), nullable=False)
    notes: Mapped[str] = mapped_column(Text, nullable=False, default="")


class AiSimulationPortfolioRecord(Base, TimestampedRecord):
    __tablename__ = "ai_simulation_portfolios"
    __table_args__ = {"schema": SCHEMA}

    portfolio_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    market: Mapped[str] = mapped_column(String(32), nullable=False)
    currency: Mapped[str] = mapped_column(String(8), nullable=False)
    initial_capital: Mapped[Decimal] = mapped_column(Numeric(24, 8), nullable=False)
    cash_balance: Mapped[Decimal] = mapped_column(Numeric(24, 8), nullable=False)
    max_positions: Mapped[int] = mapped_column(Integer, nullable=False)
    strategy_id: Mapped[str | None] = mapped_column(
        ForeignKey(f"{SCHEMA}.strategy_profiles.strategy_id"), nullable=True
    )
    strategy_ids: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="active")


class AiSimulationPositionRecord(Base, TimestampedRecord):
    __tablename__ = "ai_simulation_positions"
    __table_args__ = (
        Index("ix_ai_simulation_positions_portfolio_status", "portfolio_id", "status"),
        {"schema": SCHEMA},
    )

    position_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    portfolio_id: Mapped[str] = mapped_column(
        ForeignKey(f"{SCHEMA}.ai_simulation_portfolios.portfolio_id", ondelete="CASCADE"),
        nullable=False,
    )
    symbol: Mapped[str] = mapped_column(String(64), nullable=False)
    market: Mapped[str] = mapped_column(String(32), nullable=False)
    instrument_type: Mapped[str] = mapped_column(String(32), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(28, 8), nullable=False)
    average_cost: Mapped[Decimal] = mapped_column(Numeric(24, 8), nullable=False)
    opened_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    candidate_score: Mapped[Decimal] = mapped_column(Numeric(8, 2), nullable=False)
    factor_context: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    rationale: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="open")


class AiSimulationTradeRecord(Base):
    __tablename__ = "ai_simulation_trades"
    __table_args__ = (
        Index("ix_ai_simulation_trades_portfolio_executed", "portfolio_id", "executed_at"),
        {"schema": SCHEMA},
    )

    trade_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    portfolio_id: Mapped[str] = mapped_column(
        ForeignKey(f"{SCHEMA}.ai_simulation_portfolios.portfolio_id", ondelete="CASCADE"),
        nullable=False,
    )
    position_id: Mapped[str | None] = mapped_column(
        ForeignKey(f"{SCHEMA}.ai_simulation_positions.position_id", ondelete="SET NULL"),
        nullable=True,
    )
    side: Mapped[str] = mapped_column(String(8), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(28, 8), nullable=False)
    price: Mapped[Decimal] = mapped_column(Numeric(24, 8), nullable=False)
    executed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    rationale: Mapped[list[str]] = mapped_column(JSON, nullable=False)


class AiSimulationRunRecord(Base):
    __tablename__ = "ai_simulation_runs"
    __table_args__ = (
        Index("ix_ai_simulation_runs_portfolio_completed", "portfolio_id", "completed_at"),
        {"schema": SCHEMA},
    )

    run_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    portfolio_id: Mapped[str] = mapped_column(
        ForeignKey(f"{SCHEMA}.ai_simulation_portfolios.portfolio_id", ondelete="CASCADE"),
        nullable=False,
    )
    market: Mapped[str] = mapped_column(String(32), nullable=False)
    trigger: Mapped[str] = mapped_column(String(16), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    position_count: Mapped[int] = mapped_column(Integer, nullable=False)
    total_equity: Mapped[Decimal | None] = mapped_column(Numeric(24, 8))
    decision_reports: Mapped[list[dict[str, object]]] = mapped_column(JSON, nullable=False)
    notices: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text)


class DocumentRecord(Base, TimestampedRecord):
    __tablename__ = "documents"
    __table_args__ = {"schema": SCHEMA}

    document_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    media_type: Mapped[str] = mapped_column(String(128), nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    storage_key: Mapped[str] = mapped_column(String(512), nullable=False, unique=True)
    extraction_status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")
    extracted_text: Mapped[str | None] = mapped_column(Text)


class TradeJournalRecord(Base, TimestampedRecord):
    __tablename__ = "trade_journal_records"
    __table_args__ = {"schema": SCHEMA}

    record_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    imported_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    traded_on: Mapped[date] = mapped_column(Date, nullable=False)
    market: Mapped[str] = mapped_column(String(32), nullable=False)
    symbol: Mapped[str] = mapped_column(String(64), nullable=False)
    side: Mapped[str] = mapped_column(String(8), nullable=False)
    quantity: Mapped[str] = mapped_column(String(64), nullable=False)
    price: Mapped[str] = mapped_column(String(64), nullable=False)
    currency: Mapped[str] = mapped_column(String(8), nullable=False)
    fees: Mapped[str] = mapped_column(String(64), nullable=False, default="0")
    tags: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    note: Mapped[str | None] = mapped_column(Text)


class StrategyRunRecord(Base, TimestampedRecord):
    __tablename__ = "strategy_runs"
    __table_args__ = {"schema": SCHEMA}

    run_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    strategy_id: Mapped[str] = mapped_column(
        ForeignKey(f"{SCHEMA}.strategy_profiles.strategy_id"), nullable=False
    )
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    metrics: Mapped[dict[str, Any] | None] = mapped_column(JSON)


class MarketScanRunRecord(Base, TimestampedRecord):
    __tablename__ = "market_scan_runs"
    __table_args__ = (
        Index("ix_market_scan_runs_market_started", "market", "started_at"),
        Index("ix_market_scan_runs_completed_at", "completed_at"),
        {"schema": SCHEMA},
    )

    run_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    market: Mapped[str] = mapped_column(String(32), nullable=False)
    source: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    universe_size: Mapped[int] = mapped_column(Integer, nullable=False)
    snapshot_count: Mapped[int] = mapped_column(Integer, nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text)


class MarketSnapshotRecord(Base):
    __tablename__ = "market_snapshots"
    __table_args__ = (
        Index("ix_market_snapshots_run_symbol", "run_id", "symbol"),
        Index("ix_market_snapshots_observed_at", "observed_at"),
        {"schema": SCHEMA},
    )

    snapshot_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(
        ForeignKey(f"{SCHEMA}.market_scan_runs.run_id", ondelete="CASCADE"), nullable=False
    )
    market: Mapped[str] = mapped_column(String(32), nullable=False)
    symbol: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    source: Mapped[str] = mapped_column(String(64), nullable=False)
    last_price: Mapped[Decimal] = mapped_column(Numeric(24, 8), nullable=False)
    previous_close: Mapped[Decimal | None] = mapped_column(Numeric(24, 8))
    open_price: Mapped[Decimal | None] = mapped_column(Numeric(24, 8))
    high_price: Mapped[Decimal | None] = mapped_column(Numeric(24, 8))
    low_price: Mapped[Decimal | None] = mapped_column(Numeric(24, 8))
    volume: Mapped[Decimal | None] = mapped_column(Numeric(28, 4))
    turnover: Mapped[Decimal | None] = mapped_column(Numeric(28, 4))
    change_percent: Mapped[Decimal | None] = mapped_column(Numeric(16, 8))
    price_to_earnings: Mapped[Decimal | None] = mapped_column(Numeric(20, 8))
    price_to_book: Mapped[Decimal | None] = mapped_column(Numeric(20, 8))
