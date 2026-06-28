from datetime import datetime, timedelta
from decimal import Decimal

from app.models import CandleCache
from app.services.code_contract import FEATURE_KEYS
from app.services.feature_engine import FeatureEngine

_BASE = datetime(2026, 6, 28, 0, 0)


def candle(index: int, open_price: str, high: str, low: str, close: str, volume: str) -> CandleCache:
    return CandleCache(
        market="KRW-BTC",
        timeframe="15m",
        candle_time=_BASE + timedelta(minutes=15 * index),
        open=Decimal(open_price),
        high=Decimal(high),
        low=Decimal(low),
        close=Decimal(close),
        volume=Decimal(volume),
        trade_price=Decimal(close) * Decimal(volume),
    )


def _series(n: int = 40) -> list[CandleCache]:
    out = []
    price = 100.0
    for i in range(n):
        price *= 1.01 if i % 2 == 0 else 0.995
        out.append(candle(i, f"{price:.2f}", f"{price * 1.01:.2f}", f"{price * 0.99:.2f}", f"{price:.2f}", str(10 + i)))
    return out


def test_build_frame_emits_canonical_features_sorted_by_time():
    candles = _series(40)
    # shuffle order to confirm sorting
    frame = FeatureEngine.build_frame(list(reversed(candles)))

    assert list(frame["candle_time"]) == sorted(frame["candle_time"])
    assert set(FEATURE_KEYS).issubset(frame.columns)
    # rsi bounded, ma_align is one of the three labels
    assert frame["rsi14"].between(0, 100).all()
    assert set(frame["ma_align"].unique()).issubset({"정배열", "역배열", "혼조"})


def test_latest_features_returns_all_keys_and_is_json_safe():
    feats = FeatureEngine.latest_features(_series(40))
    assert set(feats.keys()) == set(FEATURE_KEYS)
    assert isinstance(feats["ma_align"], str)
    # numeric features are float or None (never NaN)
    for key in FEATURE_KEYS:
        if key == "ma_align":
            continue
        assert feats[key] is None or isinstance(feats[key], (int, float))


def test_feature_rows_include_ohlcv_and_features():
    rows = FeatureEngine.feature_rows(_series(30))
    assert len(rows) == 30
    sample = rows[-1]
    for key in ("candle_time", "open", "high", "low", "close", "volume"):
        assert key in sample
    assert set(FEATURE_KEYS).issubset(sample.keys())


def test_empty_candles_returns_empty_frame():
    frame = FeatureEngine.build_frame([])
    assert frame.empty
    assert FeatureEngine.latest_features([]) == {}
