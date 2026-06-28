from enum import StrEnum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class Decision(StrEnum):
    BUY = "buy"
    SELL = "sell"
    HOLD = "hold"
    WAIT = "wait"
    ADD_POSITION = "add_position"
    TAKE_PROFIT = "take_profit"
    STOP_LOSS = "stop_loss"
    UNCERTAIN = "uncertain"


class FeedbackType(StrEnum):
    ENTRY_TOO_AGGRESSIVE = "entry_too_aggressive"
    ENTRY_TOO_LATE = "entry_too_late"
    EXIT_TOO_EARLY = "exit_too_early"
    EXIT_TOO_LATE = "exit_too_late"
    RISK_TOO_HIGH = "risk_too_high"
    MISSED_GOOD_ENTRY = "missed_good_entry"
    NOT_ME = "not_me"


class MessageResponse(BaseModel):
    message: str


class ScenarioItem(BaseModel):
    id: str
    market: str
    timeframe: str
    description: str
    features_snapshot: dict[str, Any] = Field(default_factory=dict)
    chart_data: list[dict[str, Any]] = Field(default_factory=list)


class ScenarioListResponse(BaseModel):
    items: list[ScenarioItem] = Field(default_factory=list)


class UserResponseCreate(BaseModel):
    scenario_id: UUID
    decision: Decision
    natural_reason: str
    confidence: float = Field(ge=0, le=1)
    preferred_action: str


class UserResponseItem(BaseModel):
    id: str
    scenario_id: str
    decision: Decision
    natural_reason: str
    confidence: float
    preferred_action: str


class UserResponseWriteResponse(BaseModel):
    response_id: str
    response_count: int
    can_generate_twin: bool


class UserResponseListResponse(BaseModel):
    response_count: int
    can_generate_twin: bool
    items: list[UserResponseItem] = Field(default_factory=list)


class TwinContextSchema(BaseModel):
    style_summary: str = Field(min_length=1)
    important_signals: list[str] = Field(min_length=1)
    avoid_conditions: list[str] = Field(min_length=1)
    uncertainty: list[str] = Field(min_length=1)
    decision_profile: dict[str, int] = Field(default_factory=dict)
    confidence_profile: dict[str, float | str] = Field(default_factory=dict)


class TwinContextGenerateResponse(BaseModel):
    context_id: str | None = None
    version: int | None = None
    style_summary: str | None = None
    important_signals: list[str] = Field(default_factory=list)
    avoid_conditions: list[str] = Field(default_factory=list)
    uncertainty: list[str] = Field(default_factory=list)


class StrategyGenerateRequest(BaseModel):
    context_id: UUID


class StrategyRule(BaseModel):
    feature: str
    operator: str
    threshold: float | None = Field(default=None, ge=0)
    lower: float | None = Field(default=None, ge=0)
    upper: float | None = Field(default=None, ge=0)
    weight: float = Field(gt=0, le=1)


class StrategyRisk(BaseModel):
    stop_loss_pct: float = Field(gt=0, le=0.2)
    take_profit_pct: float = Field(gt=0, le=0.5)
    max_daily_entries: int = Field(ge=1, le=20)


class StrategyJSON(BaseModel):
    strategy_name: str = Field(min_length=1)
    summary: str = Field(min_length=1)
    timeframe: str = Field(min_length=1)
    entry_threshold: float = Field(ge=0, le=1)
    position_size: float = Field(gt=0, le=1)
    rules: list[StrategyRule] = Field(min_length=1)
    risk: StrategyRisk


class StrategyGenerateResponse(BaseModel):
    strategy_id: str | None = None
    version: int | None = None
    strategy_name: str | None = None
    entry_threshold: float | None = None
    summary: str


class BacktestRunRequest(BaseModel):
    strategy_id: UUID
    market: str
    timeframe: str
    period_start: str
    period_end: str
    initial_cash: float


class FeedbackCreate(BaseModel):
    target_type: str
    target_id: UUID
    feedback_type: FeedbackType
    feedback_text: str | None = None


class WatchlistCreate(BaseModel):
    strategy_id: UUID
    market: str
    timeframe: str
    cooldown_minutes: int = Field(ge=1, le=1440)


class SignalListResponse(BaseModel):
    items: list[dict[str, Any]] = Field(default_factory=list)
