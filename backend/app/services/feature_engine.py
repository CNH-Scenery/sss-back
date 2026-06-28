from typing import Iterable

import pandas as pd

from app.models import CandleCache

REQUIRED_FEATURE_COLUMNS = [
    "market",
    "timeframe",
    "candle_time",
    "open",
    "high",
    "low",
    "close",
    "volume",
    "trade_price",
    "price_return_n",
    "volume_ratio_n",
    "moving_average_slope",
    "volatility_n",
    "recent_high_breakout",
    "recent_low_breakdown",
    "upper_wick_ratio",
    "lower_wick_ratio",
    "drawdown_from_recent_high",
    "support_break",
    "rsi_14",
]


class FeatureEngine:
    @staticmethod
    def build_frame(candles: Iterable[CandleCache], lookback: int = 14) -> pd.DataFrame:
        rows = [
            {
                "market": candle.market,
                "timeframe": candle.timeframe,
                "candle_time": candle.candle_time,
                "open": float(candle.open),
                "high": float(candle.high),
                "low": float(candle.low),
                "close": float(candle.close),
                "volume": float(candle.volume),
                "trade_price": float(candle.trade_price),
            }
            for candle in candles
        ]
        if not rows:
            return pd.DataFrame(columns=REQUIRED_FEATURE_COLUMNS)

        frame = pd.DataFrame(rows).sort_values("candle_time").reset_index(drop=True)
        rolling_high = frame["high"].rolling(lookback, min_periods=1).max()
        rolling_low = frame["low"].rolling(lookback, min_periods=1).min()
        previous_high = rolling_high.shift(1)
        previous_low = rolling_low.shift(1)

        frame["price_return_n"] = frame["close"].pct_change().fillna(0.0)
        average_volume = frame["volume"].rolling(lookback, min_periods=1).mean()
        frame["volume_ratio_n"] = (frame["volume"] / average_volume).fillna(0.0)
        moving_average = frame["close"].rolling(lookback, min_periods=1).mean()
        frame["moving_average_slope"] = moving_average.pct_change().fillna(0.0)
        frame["volatility_n"] = frame["price_return_n"].rolling(lookback, min_periods=1).std().fillna(0.0)
        frame["recent_high_breakout"] = (frame["close"] >= previous_high).fillna(False).astype(float)
        frame["recent_low_breakdown"] = (frame["close"] <= previous_low).fillna(False).astype(float)

        candle_range = (frame["high"] - frame["low"]).replace(0, pd.NA)
        frame["upper_wick_ratio"] = (
            (frame["high"] - frame[["open", "close"]].max(axis=1)) / candle_range
        ).fillna(0.0)
        frame["lower_wick_ratio"] = (
            (frame[["open", "close"]].min(axis=1) - frame["low"]) / candle_range
        ).fillna(0.0)
        frame["drawdown_from_recent_high"] = ((rolling_high - frame["close"]) / rolling_high).fillna(0.0)
        frame["support_break"] = (frame["close"] < previous_low).fillna(False).astype(float)
        frame["rsi_14"] = FeatureEngine._rsi(frame["close"], window=14)

        return frame[REQUIRED_FEATURE_COLUMNS]

    @staticmethod
    def _rsi(close: pd.Series, window: int) -> pd.Series:
        delta = close.diff()
        gain = delta.clip(lower=0)
        loss = -delta.clip(upper=0)
        average_gain = gain.rolling(window, min_periods=1).mean()
        average_loss = loss.rolling(window, min_periods=1).mean()
        relative_strength = average_gain / average_loss.replace(0, pd.NA)
        rsi = 100 - (100 / (1 + relative_strength))
        return rsi.fillna(100.0).clip(lower=0, upper=100)
