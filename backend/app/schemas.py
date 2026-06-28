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
    chart_data: list[dict[str, Any]] = Field(default_factory=list)


class ScenarioListResponse(BaseModel):
    items: list[ScenarioItem] = Field(default_factory=list)


class UserResponseCreate(BaseModel):
    scenario_id: UUID
    decision: Decision
    natural_reason: str
    confidence: float = Field(ge=0, le=1)
    preferred_action: str


class TwinContextGenerateResponse(BaseModel):
    context_id: str | None = None
    version: int | None = None
    style_summary: str | None = None
    important_signals: list[str] = Field(default_factory=list)
    avoid_conditions: list[str] = Field(default_factory=list)
    uncertainty: list[str] = Field(default_factory=list)


class StrategyGenerateRequest(BaseModel):
    context_id: UUID


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
