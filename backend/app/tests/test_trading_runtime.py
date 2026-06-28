from datetime import datetime, timedelta, timezone

from app.services.trading_runtime import TradingRuntime


def normalized_candle(market: str, candle_time: datetime, price: float, volume: float = 1.0):
    return {
        "market": market,
        "timeframe": "1d",
        "candle_time": candle_time.isoformat(),
        "open": price,
        "high": price + 1,
        "low": price - 1,
        "close": price,
        "volume": volume,
        "trade_price": price * volume,
    }


class FakeUpbitClient:
    def __init__(self) -> None:
        latest = datetime(2026, 6, 28, tzinfo=timezone.utc)
        self.daily = [
            normalized_candle("KRW-BTC", latest - timedelta(days=index), 100 + (364 - index))
            for index in range(365)
        ]
        latest_minute = datetime(2026, 6, 28, 3, 15, tzinfo=timezone.utc)
        self.minutes = [
            {
                **normalized_candle(
                    "KRW-BTC",
                    latest_minute - timedelta(minutes=index),
                    100 + (119 - index),
                ),
                "timeframe": "1m",
            }
            for index in range(120)
        ]

    def list_daily_candles(self, market: str, count: int, to: str | None = None):
        assert market == "KRW-BTC"
        start = 0
        if to:
            cursor = datetime.fromisoformat(to.replace("Z", "+00:00"))
            start = next(
                index
                for index, row in enumerate(self.daily)
                if datetime.fromisoformat(row["candle_time"]) < cursor
            )
        return self.daily[start : start + count]

    def list_minute_candles(self, market: str, unit: int, count: int, to: str | None = None):
        assert market == "KRW-BTC"
        assert unit == 1
        return self.minutes[:count]

    def get_ticker(self, markets: list[str]):
        assert markets == ["KRW-BTC"]
        return [{"market": "KRW-BTC", "trade_price": 220}]


def test_run_backtest_fetches_upbit_and_returns_frontend_shape():
    runtime = TradingRuntime(upbit=FakeUpbitClient())

    result = runtime.run_backtest(
        market="btc",
        start_date="2026-01-01",
        end_date="2026-06-28",
        strategy_params={"rsiBuy": 101, "volBuy": 0, "rsiSell": 101},
    )

    assert result["source"] == "backend-upbit"
    assert len(result["chartCandles"]) == 200
    assert result["backtest"]["summary"]["market"] == "KRW-BTC"
    assert result["backtest"]["metrics"]["trades"] > 0
    assert {"rangeKey", "candles", "markers", "eq", "bh", "metrics"}.issubset(
        result["backtest"]
    )


def test_evaluate_monitor_runs_strategy_and_returns_next_position():
    runtime = TradingRuntime(upbit=FakeUpbitClient())

    result = runtime.evaluate_monitor(
        market="KRW-BTC",
        strategy_params={"rsiBuy": 101, "volBuy": 0},
        position={"holding": False, "entry": 0},
    )

    assert result["price"] == 220
    assert result["signal"] == "BUY"
    assert result["position"] == {"holding": True, "entry": 220}
    assert result["fired"] == {"sig": "BUY", "reason": result["signalReason"]}
    assert len(result["candles"]) == 120
