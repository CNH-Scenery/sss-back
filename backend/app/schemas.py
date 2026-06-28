import re
from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

EMAIL_PATTERN = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


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


class SignupRequest(BaseModel):
    name: str = Field(min_length=1)
    email: str
    password: str = Field(min_length=8)

    @field_validator("name")
    @classmethod
    def _strip_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("이름을 입력하세요.")
        return value

    @field_validator("email")
    @classmethod
    def _normalize_email(cls, value: str) -> str:
        value = value.strip().lower()
        if not EMAIL_PATTERN.match(value):
            raise ValueError("올바른 이메일 형식이 아닙니다.")
        return value


class LoginRequest(BaseModel):
    email: str
    password: str

    @field_validator("email")
    @classmethod
    def _normalize_email(cls, value: str) -> str:
        return value.strip().lower()


class UserPublic(BaseModel):
    id: str
    name: str | None = None
    email: str | None = None


class AuthTokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserPublic


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


class TradingDecision(BaseModel):
    """The object returned by the generated decide(features, position) function.

    The single canonical decision shape used across generation, live monitoring and
    backtesting. action is normalized to upper-case BUY/SELL/HOLD.
    """

    action: str
    size_ratio: float = Field(default=0.0, ge=0, le=1)
    reason: str = ""
    indicators: dict[str, Any] = Field(default_factory=dict)

    @field_validator("action")
    @classmethod
    def _action_allowed(cls, value: str) -> str:
        normalized = str(value).strip().upper()
        if normalized not in {"BUY", "SELL", "HOLD"}:
            raise ValueError("action must be one of ['BUY', 'SELL', 'HOLD']")
        return normalized


class CodeBacktestRequest(BaseModel):
    code_id: UUID
    market: str = "KRW-BTC"
    timeframe: str = "1d"  # "1d" | "15m" | "60m"
    start: str | None = None  # ISO date/datetime; if omitted, uses lookback
    end: str | None = None
    initial_cash: float = Field(default=1_000_000.0, gt=0)
    lookback: int = Field(default=365, ge=10, le=2000)  # bars when start/end omitted


class BacktestMetrics(BaseModel):
    totalReturn: float
    bhReturn: float
    winRate: float
    trades: int
    mdd: float
    vsBH: float


class BacktestResultResponse(BaseModel):
    backtest_run_id: str | None = None
    code_id: str
    market: str
    timeframe: str
    period_start: str | None = None
    period_end: str | None = None
    metrics: BacktestMetrics
    eq: list[float] = Field(default_factory=list)       # normalized strategy equity (starts ~1.0)
    bh: list[float] = Field(default_factory=list)        # normalized buy & hold curve
    candles: list[dict[str, Any]] = Field(default_factory=list)  # [{t, o, h, l, c}] per bar
    markers: list[dict[str, Any]] = Field(default_factory=list)  # [{i, type:"BUY"|"SELL"}]


class CodeGenerateRequest(BaseModel):
    prompt: str = Field(min_length=1)
    max_iterations: int | None = Field(default=None, ge=1, le=10)


class CodeGenerateResponse(BaseModel):
    code_id: str | None = None
    status: str
    passed: bool
    iterations: int
    model_name: str
    code: str
    verification: dict[str, Any]
    decision_sample: dict[str, Any] | None = None


class TradingCodeRunResponse(BaseModel):
    """One execution of a stored trading-code script."""

    run_id: str
    code_id: str
    status: str  # "ok" | "error"
    decision: str | None = None  # "buy" | "reject"
    error: str | None = None
    executed_at: datetime


class SignalListResponse(BaseModel):
    items: list[dict[str, Any]] = Field(default_factory=list)
