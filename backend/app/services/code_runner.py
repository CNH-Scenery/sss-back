"""Executes a stored `decide` function once on a given feature snapshot.

Used by the live monitor (run + WebSocket stream). Backtesting uses
strategy_engine.backtest directly.
"""
from dataclasses import dataclass
from typing import Any

from pydantic import ValidationError

from app.schemas import Decision
from app.services import strategy_engine


@dataclass
class RunOutcome:
    status: str  # "ok" | "error"
    decision: dict[str, Any] | None  # full Decision dict when ok
    error: str | None


def run_once(code: str, features: dict[str, Any], position: dict[str, Any] | None = None) -> RunOutcome:
    result = strategy_engine.evaluate(code, [{"features": features, "position": position}])
    if "engine_error" in result:
        return RunOutcome("error", None, result["engine_error"])

    probe = result.get("results", [{}])[0]
    if not probe.get("ok"):
        return RunOutcome("error", None, probe.get("error", "decide raised"))
    try:
        decision = Decision.model_validate(probe["decision"])
    except ValidationError as exc:
        return RunOutcome("error", None, f"decision does not match contract: {exc}")
    return RunOutcome("ok", decision.model_dump(), None)
