"""Turns candles into the canonical Features dict the `decide` contract reads.

The output keys are FEATURE_KEYS (code_contract) — kept in lockstep with the frontend
feature snapshot so generated code, live monitor, backtester and UI all agree.
"""
from typing import Any, Iterable

import math

import pandas as pd

from app.models import CandleCache
from app.services.code_contract import FEATURE_KEYS

_OHLCV = ["candle_time", "open", "high", "low", "close", "volume"]


def _candle_to_row(candle: Any) -> dict[str, Any]:
    if isinstance(candle, dict):
        return {
            "candle_time": candle["candle_time"],
            "open": float(candle["open"]),
            "high": float(candle["high"]),
            "low": float(candle["low"]),
            "close": float(candle["close"]),
            "volume": float(candle["volume"]),
        }
    return {
        "candle_time": candle.candle_time,
        "open": float(candle.open),
        "high": float(candle.high),
        "low": float(candle.low),
        "close": float(candle.close),
        "volume": float(candle.volume),
    }


def _clean(value: Any) -> Any:
    """Make a cell JSON-safe: NaN/inf -> None, numpy scalars -> python floats."""
    if isinstance(value, str):
        return value
    try:
        if value is None or (isinstance(value, float) and (math.isnan(value) or math.isinf(value))):
            return None
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        return value
    if isinstance(value, (int,)):
        return int(value)
    return float(value)


class FeatureEngine:
    @staticmethod
    def build_frame(candles: Iterable[Any]) -> pd.DataFrame:
        rows = [_candle_to_row(c) for c in candles]
        columns = _OHLCV + [k for k in FEATURE_KEYS if k not in _OHLCV]
        if not rows:
            return pd.DataFrame(columns=columns)

        f = pd.DataFrame(rows).sort_values("candle_time").reset_index(drop=True)
        close = f["close"]

        f["rsi14"] = FeatureEngine._rsi(close, 14)

        avg_vol = f["volume"].rolling(20, min_periods=1).mean()
        f["vol_ratio"] = (f["volume"] / avg_vol.replace(0, pd.NA))

        for window in (5, 7, 20, 25, 30, 60, 99, 120):
            f[f"ma{window}"] = close.rolling(window, min_periods=1).mean()

        up = (f["ma5"] >= f["ma20"]) & (f["ma20"] >= f["ma60"]) & (f["ma60"] >= f["ma120"])
        down = (f["ma5"] <= f["ma20"]) & (f["ma20"] <= f["ma60"]) & (f["ma60"] <= f["ma120"])
        f["ma_align"] = "혼조"
        f.loc[up, "ma_align"] = "정배열"
        f.loc[down, "ma_align"] = "역배열"

        ema12 = close.ewm(span=12, adjust=False).mean()
        ema26 = close.ewm(span=26, adjust=False).mean()
        f["macd"] = ema12 - ema26

        mid = close.rolling(20, min_periods=1).mean()
        std = close.rolling(20, min_periods=1).std().fillna(0.0)
        upper = mid + 2 * std
        lower = mid - 2 * std
        band = (upper - lower).replace(0, pd.NA)
        f["bb_pct"] = (close - lower) / band
        f["bb_width"] = band / mid.replace(0, pd.NA)

        f["atr"] = FeatureEngine._atr(f, 14)
        f["atr_pct"] = (f["atr"] / close.replace(0, pd.NA)) * 100

        high20 = f["high"].rolling(20, min_periods=1).max()
        low20 = f["low"].rolling(20, min_periods=1).min()
        f["dist_from_high20"] = (close - high20) / high20.replace(0, pd.NA) * 100
        f["dist_from_low20"] = (close - low20) / low20.replace(0, pd.NA) * 100

        return f[columns]

    @staticmethod
    def latest_features(candles: Iterable[Any]) -> dict[str, Any]:
        """The most recent bar's features (for live decisions). {} if no data."""
        frame = FeatureEngine.build_frame(candles)
        if frame.empty:
            return {}
        last = frame.iloc[-1]
        return {key: _clean(last[key]) for key in FEATURE_KEYS}

    @staticmethod
    def feature_rows(candles: Iterable[Any]) -> list[dict[str, Any]]:
        """Every bar as {candle_time, open, high, low, close, volume, **features} —
        for the backtester (features for decide, OHLCV for fills)."""
        frame = FeatureEngine.build_frame(candles)
        out: list[dict[str, Any]] = []
        for _, row in frame.iterrows():
            record = {col: _clean(row[col]) for col in frame.columns if col != "candle_time"}
            ts = row["candle_time"]
            record["candle_time"] = ts.isoformat() if hasattr(ts, "isoformat") else str(ts)
            out.append(record)
        return out

    @staticmethod
    def _rsi(close: pd.Series, window: int) -> pd.Series:
        delta = close.diff()
        gain = delta.clip(lower=0)
        loss = -delta.clip(upper=0)
        avg_gain = gain.rolling(window, min_periods=1).mean()
        avg_loss = loss.rolling(window, min_periods=1).mean()
        rs = avg_gain / avg_loss.replace(0, pd.NA)
        rsi = 100 - (100 / (1 + rs))
        return rsi.fillna(100.0).clip(lower=0, upper=100)

    @staticmethod
    def _atr(frame: pd.DataFrame, window: int) -> pd.Series:
        prev_close = frame["close"].shift(1)
        tr = pd.concat(
            [
                frame["high"] - frame["low"],
                (frame["high"] - prev_close).abs(),
                (frame["low"] - prev_close).abs(),
            ],
            axis=1,
        ).max(axis=1)
        return tr.rolling(window, min_periods=1).mean()
