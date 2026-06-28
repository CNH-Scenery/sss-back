from datetime import datetime
from decimal import Decimal

import pytest

from app.models import CandleCache
from app.services.feature_engine import FeatureEngine, REQUIRED_FEATURE_COLUMNS


def candle(index: int, open_price: str, high: str, low: str, close: str, volume: str) -> CandleCache:
    return CandleCache(
        market="KRW-BTC",
        timeframe="15m",
        candle_time=datetime(2026, 6, 28, 3, index * 15),
        open=Decimal(open_price),
        high=Decimal(high),
        low=Decimal(low),
        close=Decimal(close),
        volume=Decimal(volume),
        trade_price=Decimal(close) * Decimal(volume),
    )


def test_feature_engine_returns_required_columns_and_sorts_by_time():
    candles = [
        candle(2, "102", "106", "101", "105", "14"),
        candle(0, "100", "105", "98", "101", "10"),
        candle(1, "101", "104", "99", "102", "12"),
        candle(3, "105", "108", "103", "104", "13"),
    ]

    frame = FeatureEngine.build_frame(candles, lookback=3)

    assert list(frame["candle_time"]) == sorted(frame["candle_time"])
    assert set(REQUIRED_FEATURE_COLUMNS).issubset(frame.columns)
    assert frame.loc[1, "price_return_n"] == pytest.approx((102 - 101) / 101)
    assert frame.loc[0, "upper_wick_ratio"] == pytest.approx((105 - 101) / (105 - 98))
    assert frame.loc[0, "lower_wick_ratio"] == pytest.approx((100 - 98) / (105 - 98))


def test_feature_engine_returns_empty_frame_with_required_columns():
    frame = FeatureEngine.build_frame([])

    assert frame.empty
    assert list(frame.columns) == REQUIRED_FEATURE_COLUMNS
