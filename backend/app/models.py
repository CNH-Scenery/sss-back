from datetime import datetime, timezone
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, Column, Index, JSON, UniqueConstraint, text
from sqlmodel import Field, SQLModel


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class User(SQLModel, table=True):
    __tablename__ = "users"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    nickname: str | None = None
    risk_profile: str | None = None
    default_timeframe: str | None = None
    created_at: datetime = Field(default_factory=utc_now)


class Scenario(SQLModel, table=True):
    __tablename__ = "scenarios"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    market: str
    timeframe: str
    window_start: datetime | None = None
    window_end: datetime | None = None
    description: str
    features_snapshot: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    chart_data: list[dict[str, Any]] = Field(default_factory=list, sa_column=Column(JSON))
    hidden_future_data: dict[str, Any] | None = Field(default=None, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=utc_now)


class UserResponse(SQLModel, table=True):
    __tablename__ = "user_responses"
    __table_args__ = (
        UniqueConstraint("user_id", "scenario_id", name="uq_user_response_once"),
        CheckConstraint("confidence >= 0 AND confidence <= 1", name="ck_response_confidence"),
    )

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    user_id: UUID = Field(foreign_key="users.id")
    scenario_id: UUID = Field(foreign_key="scenarios.id")
    decision: str
    natural_reason: str
    confidence: float
    preferred_action: str
    created_at: datetime = Field(default_factory=utc_now)


class TwinContext(SQLModel, table=True):
    __tablename__ = "twin_contexts"
    __table_args__ = (Index("uq_twin_context_version", "user_id", "version", unique=True),)

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    user_id: UUID = Field(foreign_key="users.id")
    version: int
    source_response_ids: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    style_summary: str
    context_json: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    uncertainty_json: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=utc_now)


class TwinStrategy(SQLModel, table=True):
    __tablename__ = "twin_strategies"
    __table_args__ = (
        Index("uq_twin_strategy_version", "user_id", "version", unique=True),
        Index(
            "uq_active_strategy_per_user",
            "user_id",
            unique=True,
            sqlite_where=text("is_active = 1"),
            postgresql_where=text("is_active = true"),
        ),
    )

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    user_id: UUID = Field(foreign_key="users.id")
    context_id: UUID = Field(foreign_key="twin_contexts.id")
    version: int
    strategy_name: str
    strategy_json: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    status: str
    is_active: bool = False
    created_at: datetime = Field(default_factory=utc_now)


class CandleCache(SQLModel, table=True):
    __tablename__ = "candle_cache"
    __table_args__ = (
        UniqueConstraint("market", "timeframe", "candle_time", name="uq_candle_cache_key"),
    )

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    market: str
    timeframe: str
    candle_time: datetime
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: Decimal
    trade_price: Decimal
    created_at: datetime = Field(default_factory=utc_now)


class BacktestRun(SQLModel, table=True):
    __tablename__ = "backtest_runs"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    user_id: UUID = Field(foreign_key="users.id")
    strategy_id: UUID = Field(foreign_key="twin_strategies.id")
    market: str
    timeframe: str
    period_start: datetime
    period_end: datetime
    initial_cash: Decimal
    final_value: Decimal
    total_return: float
    buy_and_hold_return: float
    max_drawdown: float
    win_rate: float
    trade_count: int
    summary: str
    created_at: datetime = Field(default_factory=utc_now)


class BacktestTrade(SQLModel, table=True):
    __tablename__ = "backtest_trades"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    backtest_run_id: UUID = Field(foreign_key="backtest_runs.id")
    market: str
    side: str
    entry_time: datetime | None = None
    entry_price: Decimal | None = None
    exit_time: datetime | None = None
    exit_price: Decimal | None = None
    size_ratio: float
    return_pct: float | None = None
    reason_json: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=utc_now)


class Feedback(SQLModel, table=True):
    __tablename__ = "feedbacks"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    user_id: UUID = Field(foreign_key="users.id")
    target_type: str
    target_id: UUID
    feedback_type: str
    feedback_text: str | None = None
    created_at: datetime = Field(default_factory=utc_now)


class Watchlist(SQLModel, table=True):
    __tablename__ = "watchlists"
    __table_args__ = (
        UniqueConstraint("user_id", "strategy_id", "market", "timeframe", name="uq_watchlist_target"),
        CheckConstraint("cooldown_minutes >= 1 AND cooldown_minutes <= 1440", name="ck_watchlist_cooldown"),
    )

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    user_id: UUID = Field(foreign_key="users.id")
    strategy_id: UUID = Field(foreign_key="twin_strategies.id")
    market: str
    timeframe: str
    is_active: bool
    cooldown_minutes: int
    created_at: datetime = Field(default_factory=utc_now)


class SignalEvent(SQLModel, table=True):
    __tablename__ = "signal_events"
    __table_args__ = (
        UniqueConstraint("dedup_key", name="uq_signal_dedup_key"),
        CheckConstraint("score >= 0 AND score <= 1", name="ck_signal_score"),
    )

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    user_id: UUID = Field(foreign_key="users.id")
    strategy_id: UUID = Field(foreign_key="twin_strategies.id")
    market: str
    signal_type: str
    dedup_key: str
    score: float
    reason_json: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    risk_json: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    feature_snapshot: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    status: str
    created_at: datetime = Field(default_factory=utc_now)


class SimulatedOrder(SQLModel, table=True):
    __tablename__ = "simulated_orders"
    __table_args__ = (
        UniqueConstraint("signal_event_id", name="uq_simulated_order_signal"),
        CheckConstraint("size_ratio > 0 AND size_ratio <= 1", name="ck_order_size_ratio"),
        CheckConstraint("price > 0", name="ck_order_price"),
        CheckConstraint("simulated_amount > 0", name="ck_order_amount"),
    )

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    user_id: UUID = Field(foreign_key="users.id")
    signal_event_id: UUID = Field(foreign_key="signal_events.id")
    market: str
    side: str
    price: Decimal
    size_ratio: float
    simulated_amount: Decimal
    status: str
    created_at: datetime = Field(default_factory=utc_now)
