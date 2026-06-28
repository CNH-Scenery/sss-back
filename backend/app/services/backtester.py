"""Backtests a generated `decide` function over historical Upbit candles.

Data fetching (paginated Upbit) is separated from simulation so the sim can be unit
tested with synthetic candles (no network). The simulation itself runs in
strategy_engine (sandboxed), driving decide() bar by bar.
"""
from typing import Any

from app.services.code_contract import FEATURE_KEYS
from app.services.feature_engine import FeatureEngine
from app.services.upbit_client import UpbitClient
from app.services import strategy_engine

_TIMEFRAME_MINUTE = {"15m": 15, "60m": 60}
_MAX_PER_PAGE = 200


def fetch_candles(
    market: str,
    timeframe: str,
    lookback: int,
    start: str | None = None,
    end: str | None = None,
    client: UpbitClient | None = None,
) -> list[dict[str, Any]]:
    """Gather up to `lookback` chronological candles (paginating with the `to` cursor).

    If start/end (ISO strings) are given, the collected candles are filtered to that range.
    """
    client = client or UpbitClient()
    need = max(lookback, 1)
    collected: dict[str, dict[str, Any]] = {}
    cursor = end

    while len(collected) < need:
        count = min(_MAX_PER_PAGE, need - len(collected))
        if timeframe in _TIMEFRAME_MINUTE:
            batch = client.list_minute_candles(market, _TIMEFRAME_MINUTE[timeframe], count, to=cursor)
        else:
            batch = client.list_daily_candles(market, count, to=cursor)
        if not batch:
            break
        for candle in batch:
            collected[candle["candle_time"]] = candle
        cursor = min(candle["candle_time"] for candle in batch)
        if len(batch) < count:
            break

    rows = sorted(collected.values(), key=lambda c: c["candle_time"])
    if start:
        rows = [r for r in rows if r["candle_time"] >= start]
    if end:
        rows = [r for r in rows if r["candle_time"] <= end]
    return rows


def run_backtest(code: str, candles: list[dict[str, Any]], initial_cash: float) -> dict[str, Any]:
    """Compute features per bar and run the sandboxed simulation. Returns the engine result
    ({"backtest": {...}}) or {"engine_error": ...}."""
    feature_rows = FeatureEngine.feature_rows(candles)
    if not feature_rows:
        return {"engine_error": "no candle data for the requested market/period"}
    return strategy_engine.backtest(code, feature_rows, FEATURE_KEYS, initial_cash)
