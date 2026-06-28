from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from math import ceil, floor, isfinite, sqrt
from typing import Any

from app.services.upbit_client import UpbitClient

KST = timezone(timedelta(hours=9))
MAX_DAILY_CANDLE_COUNT = 200
MAX_SECOND_CANDLE_COUNT = 200
MAX_SECOND_HISTORY_COUNT = 24 * 60 * 60
MAX_MINUTE_CANDLE_COUNT = 200
MAX_MINUTE_HISTORY_COUNT = 20000
SECOND_REQUEST_DELAY_SECONDS = 0.28
MINUTE_REQUEST_DELAY_SECONDS = 0.22


@dataclass(frozen=True)
class StrategyParams:
    rsi_buy: float = 42
    volume_buy: float = 1.05
    rsi_sell: float = 60
    take_profit_pct: float = 10
    stop_loss_pct: float = -6

    @classmethod
    def from_payload(cls, payload: dict[str, Any] | None) -> "StrategyParams":
        payload = payload or {}
        defaults = cls()
        return cls(
            rsi_buy=_number(payload.get("rsiBuy"), defaults.rsi_buy),
            volume_buy=_number(payload.get("volBuy"), defaults.volume_buy),
            rsi_sell=_number(payload.get("rsiSell"), defaults.rsi_sell),
            take_profit_pct=_number(payload.get("pnlTake"), defaults.take_profit_pct),
            stop_loss_pct=_number(payload.get("pnlStop"), defaults.stop_loss_pct),
        )


class TradingRuntime:
    def __init__(self, upbit: UpbitClient | None = None) -> None:
        self.upbit = upbit or UpbitClient()

    def fetch_chart_candles(
        self,
        market: str,
        source: str,
        *,
        count: int = 200,
        unit: int = 1,
        seconds: int = 200,
        bucket_seconds: int = 1,
    ) -> list[dict[str, Any]]:
        market = normalize_market(market)
        if source == "daily":
            return self.fetch_daily_candles(market, count)
        if source in {"week", "weekly"}:
            return self.fetch_week_candles(market, count)
        if source in {"month", "monthly"}:
            return self.fetch_month_candles(market, count)
        if source in {"year", "yearly"}:
            return self.fetch_year_candles(market, count)
        if source == "minute":
            return self.fetch_minute_candles(market, unit, count)
        if source == "second":
            return self.fetch_second_candles(market, seconds, bucket_seconds)
        raise ValueError("source must be second, minute, daily, week, month, or year")

    def fetch_daily_candles(self, market: str, days: int = 200) -> list[dict[str, Any]]:
        market = normalize_market(market)
        target_count = max(1, min(MAX_DAILY_CANDLE_COUNT, floor(_number(days, 200))))
        rows = self.upbit.list_daily_candles(market=market, count=target_count)
        candles = [_to_chart_candle(row) for row in rows]
        candles.reverse()
        if len(candles) < min(30, target_count):
            raise ValueError(f"{market} daily candle data is not enough.")
        return candles

    def fetch_week_candles(self, market: str, count: int = 200) -> list[dict[str, Any]]:
        return self._fetch_period_candles(
            market, count, self.upbit.list_week_candles, "weekly candle data"
        )

    def fetch_month_candles(self, market: str, count: int = 200) -> list[dict[str, Any]]:
        return self._fetch_period_candles(
            market, count, self.upbit.list_month_candles, "monthly candle data"
        )

    def fetch_year_candles(self, market: str, count: int = 200) -> list[dict[str, Any]]:
        return self._fetch_period_candles(
            market, count, self.upbit.list_year_candles, "yearly candle data", min_count=1
        )

    def _fetch_period_candles(
        self,
        market: str,
        count: int,
        fetcher,
        label: str,
        *,
        min_count: int = 2,
    ) -> list[dict[str, Any]]:
        market = normalize_market(market)
        target_count = max(1, min(200, floor(_number(count, 200))))
        rows = fetcher(market=market, count=target_count)
        candles = [_to_chart_candle(row) for row in rows]
        candles.reverse()
        if len(candles) < min_count:
            raise ValueError(f"{market} {label} is not enough.")
        return candles

    def fetch_minute_candles(self, market: str, unit: int = 1, count: int = 120) -> list[dict[str, Any]]:
        market = normalize_market(market)
        minute_unit = int(_number(unit, 1))
        target_count = max(1, min(MAX_MINUTE_HISTORY_COUNT, floor(_number(count, 120))))
        rows: list[dict[str, Any]] = []
        cursor = None

        while len(rows) < target_count:
            page_count = min(MAX_MINUTE_CANDLE_COUNT, target_count - len(rows))
            page = self.upbit.list_minute_candles(
                market=market,
                unit=minute_unit,
                count=page_count,
                to=cursor,
            )
            if not page:
                break
            rows.extend(page)
            oldest = page[-1]
            if len(page) < page_count:
                break
            cursor = _cursor_before(oldest["candle_time"])
            if len(rows) < target_count:
                time.sleep(MINUTE_REQUEST_DELAY_SECONDS)

        if len(rows) < 20:
            raise ValueError(f"{market} minute candle data is not enough.")
        candles = [_to_chart_candle(row, unit=minute_unit) for row in rows[:target_count]]
        candles.reverse()
        return candles

    def fetch_second_candles(
        self, market: str, seconds: int = 200, bucket_seconds: int = 1
    ) -> list[dict[str, Any]]:
        market = normalize_market(market)
        bucket_size = max(1, floor(_number(bucket_seconds, 1)))
        bucket_ms = bucket_size * 1000
        bucket_count = max(1, ceil(max(1, floor(_number(seconds, 200))) / bucket_size))
        end_ms = floor(datetime.now(timezone.utc).timestamp() * 1000 / bucket_ms) * bucket_ms
        start_ms = end_ms - (bucket_count - 1) * bucket_ms
        rows: list[dict[str, Any]] = []
        cursor = None

        while len(rows) < MAX_SECOND_HISTORY_COUNT:
            page_count = min(MAX_SECOND_CANDLE_COUNT, MAX_SECOND_HISTORY_COUNT - len(rows))
            page = self.upbit.list_second_candles(market=market, count=page_count, to=cursor)
            if not page:
                break
            rows.extend(page)
            oldest = page[-1]
            if len(page) < page_count:
                break
            oldest_ms = _parse_utc(oldest["candle_time"]).timestamp() * 1000
            if oldest_ms <= start_ms:
                break
            cursor = _cursor_before(oldest["candle_time"])
            if len(rows) < MAX_SECOND_HISTORY_COUNT:
                time.sleep(SECOND_REQUEST_DELAY_SECONDS)

        if len(rows) < 20:
            raise ValueError(f"{market} second candle data is not enough.")

        candles = [
            _to_chart_candle(row, unit=1, utc_time=row["candle_time"])
            for row in reversed(rows)
            if start_ms <= _parse_utc(row["candle_time"]).timestamp() * 1000 <= end_ms
        ]
        return _aggregate_candles_by_seconds(candles, bucket_size)

    def run_backtest(
        self,
        *,
        market: str,
        start_date: str | None,
        end_date: str | None,
        strategy_params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        market = normalize_market(market)
        params = StrategyParams.from_payload(strategy_params)
        candles = self.fetch_daily_candles(market, 200)
        backtest = _run_backtest_data(candles, market, params, start_date, end_date)
        return {
            "backtest": backtest,
            "chartCandles": candles,
            "source": "backend-upbit",
        }

    def evaluate_monitor(
        self,
        *,
        market: str,
        strategy_params: dict[str, Any] | None = None,
        position: dict[str, Any] | None = None,
        unit: int = 1,
        count: int = 120,
    ) -> dict[str, Any]:
        market = normalize_market(market)
        params = StrategyParams.from_payload(strategy_params)
        candles = self.fetch_minute_candles(market, unit, count)
        features = _features(candles)
        candle_price = round(float(candles[-1]["c"]))
        price = self._latest_price_or_fallback(market, candle_price)
        current_position = {
            "holding": bool((position or {}).get("holding")),
            "entry": _number((position or {}).get("entry"), 0),
        }
        pnl = (
            (price - current_position["entry"]) / current_position["entry"] * 100
            if current_position["holding"] and current_position["entry"]
            else 0
        )
        action = _strategy_decide(features, current_position["holding"], pnl, params)
        reason = _signal_reason(action, features, current_position["holding"])
        next_position = dict(current_position)
        fired = None
        if action == "BUY" and not current_position["holding"]:
            next_position = {"holding": True, "entry": price}
            fired = {"sig": "BUY", "reason": reason}
        elif action == "SELL" and current_position["holding"]:
            next_position = {"holding": False, "entry": current_position["entry"]}
            fired = {"sig": "SELL", "reason": reason}

        return {
            "market": market,
            "price": price,
            "signal": action,
            "signalReason": reason,
            "features": features,
            "candles": candles,
            "lastCandleTime": candles[-1].get("t", ""),
            "position": next_position,
            "fired": fired,
            "source": "backend-upbit",
        }

    def _latest_price_or_fallback(self, market: str, fallback: int) -> int:
        try:
            ticker = self.upbit.get_ticker([market])
            if ticker:
                price = round(float(ticker[0]["trade_price"]))
                if isfinite(price):
                    return price
        except Exception:
            return fallback
        return fallback


def normalize_market(value: str | None) -> str:
    market = str(value or "").strip().upper()
    if not market:
        return "KRW-BTC"
    if "-" not in market and market.replace("_", "").isalnum():
        return f"KRW-{market}"
    return market


def _number(value: Any, default: float) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return float(default)
    return number if isfinite(number) else float(default)


def _parse_utc(value: str) -> datetime:
    text = str(value)
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    parsed = datetime.fromisoformat(text)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _cursor_before(value: str) -> str:
    cursor = _parse_utc(value) - timedelta(seconds=1)
    return cursor.isoformat().replace("+00:00", "Z")


def _local_time(value: str) -> str:
    return _parse_utc(value).astimezone(KST).replace(tzinfo=None).isoformat(timespec="seconds")


def _to_chart_candle(
    row: dict[str, Any],
    *,
    unit: int | None = None,
    utc_time: str | None = None,
) -> dict[str, Any]:
    candle = {
        "t": _local_time(str(row["candle_time"])),
        "market": row["market"],
        "o": float(row["open"]),
        "h": float(row["high"]),
        "l": float(row["low"]),
        "c": float(row["close"]),
        "v": float(row["volume"]),
        "accTradePrice": float(row.get("trade_price", 0)),
    }
    if unit is not None:
        candle["unit"] = unit
    if utc_time:
        candle["utcTime"] = utc_time
    return candle


def _chart_time(candle: dict[str, Any]) -> datetime | None:
    value = candle.get("utcTime") or candle.get("t")
    if not value:
        return None
    try:
        if candle.get("utcTime"):
            return _parse_utc(str(value))
        parsed = datetime.fromisoformat(str(value).replace(" ", "T"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=KST)
        return parsed.astimezone(timezone.utc)
    except ValueError:
        return None


def _chart_time_from_ms(value: int) -> str:
    return datetime.fromtimestamp(value / 1000, tz=KST).replace(tzinfo=None).isoformat(timespec="seconds")


def _aggregate_candles_by_seconds(
    candles: list[dict[str, Any]], bucket_seconds: int
) -> list[dict[str, Any]]:
    bucket_ms = max(1, int(bucket_seconds)) * 1000
    if bucket_ms <= 1000:
        return candles

    buckets: dict[int, dict[str, Any]] = {}
    for candle in candles:
        time_value = _chart_time(candle)
        if not time_value:
            continue
        bucket_start = floor(time_value.timestamp() * 1000 / bucket_ms) * bucket_ms
        existing = buckets.get(bucket_start)
        if not existing:
            buckets[bucket_start] = {
                "t": _chart_time_from_ms(bucket_start),
                "market": candle["market"],
                "unit": bucket_seconds,
                "o": candle["o"],
                "h": candle["h"],
                "l": candle["l"],
                "c": candle["c"],
                "v": candle.get("v", 0),
                "accTradePrice": candle.get("accTradePrice", 0),
            }
            continue
        existing["h"] = max(existing["h"], candle["h"])
        existing["l"] = min(existing["l"], candle["l"])
        existing["c"] = candle["c"]
        existing["v"] += candle.get("v", 0)
        existing["accTradePrice"] += candle.get("accTradePrice", 0)

    return [candle for _, candle in sorted(buckets.items())]


def _date_only(value: str | None) -> str:
    return str(value or "")[:10]


def _rsi(closes: list[float], period: int) -> float:
    if len(closes) < period + 1:
        return 50
    average_gain = 0.0
    average_loss = 0.0
    for index in range(1, period + 1):
        delta = closes[index] - closes[index - 1]
        if delta > 0:
            average_gain += delta
        else:
            average_loss -= delta
    average_gain /= period
    average_loss /= period
    for index in range(period + 1, len(closes)):
        delta = closes[index] - closes[index - 1]
        average_gain = (average_gain * (period - 1) + (delta if delta > 0 else 0)) / period
        average_loss = (average_loss * (period - 1) + (-delta if delta < 0 else 0)) / period
    relative_strength = average_gain / (average_loss or 1e-9)
    return 100 - 100 / (1 + relative_strength)


def _features(candles: list[dict[str, Any]]) -> dict[str, Any]:
    closes = [float(item["c"]) for item in candles]
    volumes = [float(item.get("v", 0)) for item in candles]
    highs = [float(item["h"]) for item in candles]
    lows = [float(item["l"]) for item in candles]
    last = closes[-1]

    def ma(period: int) -> float:
        period = min(period, len(closes))
        values = closes[-period:]
        return sum(values) / len(values)

    ma5 = ma(5)
    ma7 = ma(7)
    ma20 = ma(20)
    ma25 = ma(25)
    ma30 = ma(30)
    ma60 = ma(min(60, len(closes)))
    ma99 = ma(min(99, len(closes)))
    ma120 = ma(min(120, len(closes)))
    if ma7 > ma25 > ma99:
        ma_align = "bull"
    elif ma7 < ma25 < ma99:
        ma_align = "bear"
    else:
        ma_align = "mixed"
    average_volume = sum(volumes[-20:]) / min(20, len(volumes))
    volume_ratio = volumes[-1] / (average_volume or 1e-9)

    def ema(period: int) -> float:
        weight = 2 / (period + 1)
        value = closes[0]
        for close in closes[1:]:
            value = close * weight + value * (1 - weight)
        return value

    macd = ema(12) - ema(26)
    recent = closes[-20:]
    mid = sum(recent) / len(recent)
    stdev = sqrt(sum((value - mid) ** 2 for value in recent) / len(recent))
    upper = mid + 2 * stdev
    lower = mid - 2 * stdev
    band_width = (upper - lower) or 1
    true_range = 0.0
    for index in range(1, len(candles)):
        true_range += max(
            highs[index] - lows[index],
            abs(highs[index] - closes[index - 1]),
            abs(lows[index] - closes[index - 1]),
        )
    atr = true_range / max(1, len(candles) - 1)
    high20 = max(highs[-20:])
    low20 = min(lows[-20:])
    return {
        "close": last,
        "rsi14": _rsi(closes, 14),
        "vol_ratio": volume_ratio,
        "ma5": ma5,
        "ma7": ma7,
        "ma20": ma20,
        "ma25": ma25,
        "ma30": ma30,
        "ma60": ma60,
        "ma99": ma99,
        "ma120": ma120,
        "ma_align": ma_align,
        "macd": macd,
        "bb_pct": (last - lower) / band_width,
        "bb_width": (upper - lower) / mid if mid else 0,
        "atr": atr,
        "atr_pct": atr / last * 100 if last else 0,
        "dist_from_high20": (last - high20) / high20 * 100 if high20 else 0,
        "dist_from_low20": (last - low20) / low20 * 100 if low20 else 0,
    }


def _features_at(candles: list[dict[str, Any]], index: int) -> dict[str, Any]:
    return _features(candles[: index + 1])


def _strategy_decide(
    features: dict[str, Any],
    holding: bool,
    pnl_pct: float,
    params: StrategyParams,
) -> str:
    if (
        not holding
        and features["rsi14"] < params.rsi_buy
        and features["vol_ratio"] > params.volume_buy
    ):
        return "BUY"
    if holding and (
        features["rsi14"] > params.rsi_sell
        or pnl_pct > params.take_profit_pct
        or pnl_pct < params.stop_loss_pct
    ):
        return "SELL"
    return "HOLD"


def _signal_reason(action: str, features: dict[str, Any], holding: bool) -> str:
    rsi = features["rsi14"]
    volume = features["vol_ratio"]
    if action == "BUY":
        return f"RSI {rsi:.0f} oversold + volume {volume:.1f}x"
    if action == "SELL":
        return f"Exit rule reached - RSI {rsi:.0f}"
    if holding:
        return f"Holding position - waiting for exit - RSI {rsi:.0f}"
    return f"Conditions not met - waiting - RSI {rsi:.0f}"


def _resolve_backtest_range(
    candles: list[dict[str, Any]], start_date: str | None, end_date: str | None
) -> dict[str, Any]:
    first = _date_only(candles[0].get("t"))
    last = _date_only(candles[-1].get("t"))
    start = start_date or first
    end = end_date or last
    if start > end:
        raise ValueError("backtest start date must be earlier than end date")
    if start < first or end > last:
        raise ValueError(f"selected date is outside available range: {first} ~ {last}")
    start_index = next((i for i, item in enumerate(candles) if _date_only(item.get("t")) >= start), -1)
    end_index = -1
    for index in range(len(candles) - 1, -1, -1):
        if _date_only(candles[index].get("t")) <= end:
            end_index = index
            break
    if start_index < 0 or end_index < start_index:
        raise ValueError("selected date range has no candle data")
    return {"start": start, "end": end, "startIndex": start_index, "endIndex": end_index}


def _run_backtest_data(
    candles: list[dict[str, Any]],
    market: str,
    params: StrategyParams,
    start_date: str | None,
    end_date: str | None,
) -> dict[str, Any]:
    resolved = _resolve_backtest_range(candles, start_date, end_date)
    start_index = resolved["startIndex"]
    end_index = resolved["endIndex"]
    closes = [float(item["c"]) for item in candles]
    holding = False
    entry = 0.0
    equity = 1.0
    equity_curve: list[float] = []
    buy_hold_curve: list[float] = []
    markers: list[dict[str, Any]] = []
    trades: list[float] = []
    first_price = closes[start_index]

    for index in range(start_index, end_index + 1):
        features = _features_at(candles, index)
        pnl = (closes[index] - entry) / entry * 100 if holding and entry else 0
        action = _strategy_decide(features, holding, pnl, params)
        if action == "BUY" and not holding:
            holding = True
            entry = closes[index]
            markers.append(
                {
                    "i": index - start_index,
                    "type": "BUY",
                    "label": "B",
                    "t": candles[index].get("t"),
                    "price": closes[index],
                }
            )
        elif action == "SELL" and holding:
            trade_return = (closes[index] - entry) / entry
            trades.append(trade_return)
            equity *= 1 + trade_return
            markers.append(
                {
                    "i": index - start_index,
                    "type": "SELL",
                    "label": "S",
                    "t": candles[index].get("t"),
                    "price": closes[index],
                }
            )
            holding = False
        current = equity * (closes[index] / entry) if holding and entry else equity
        equity_curve.append(current)
        buy_hold_curve.append(closes[index] / first_price)

    if holding and entry:
        trade_return = (closes[end_index] - entry) / entry
        trades.append(trade_return)
        equity *= 1 + trade_return

    final_equity = equity_curve[-1] if equity_curve else 1
    total_return = (final_equity - 1) * 100
    buy_hold_return = ((buy_hold_curve[-1] if buy_hold_curve else 1) - 1) * 100
    wins = len([value for value in trades if value > 0])
    win_rate = wins / len(trades) * 100 if trades else 0
    peak = float("-inf")
    max_drawdown = 0.0
    for value in equity_curve:
        peak = max(peak, value)
        drawdown = (value - peak) / peak if peak else 0
        max_drawdown = min(max_drawdown, drawdown)

    chart_candles = candles[start_index : end_index + 1]
    range_key = (
        f"{market}:{resolved['start']}:{resolved['end']}:{start_index}-{end_index}"
    )
    return {
        "rangeKey": range_key,
        "candles": chart_candles,
        "markers": markers,
        "eq": equity_curve,
        "bh": buy_hold_curve,
        "summary": {
            "market": market,
            "rangeKey": range_key,
            "fullCandleCount": len(candles),
            "rangeCandleCount": len(chart_candles),
            "dataFrom": candles[0].get("t"),
            "dataTo": candles[-1].get("t"),
            "from": chart_candles[0].get("t") if chart_candles else None,
            "to": chart_candles[-1].get("t") if chart_candles else None,
            "requestedFrom": resolved["start"],
            "requestedTo": resolved["end"],
            "source": "Backend Upbit daily",
        },
        "metrics": {
            "totalReturn": total_return,
            "bhReturn": buy_hold_return,
            "winRate": win_rate,
            "trades": len(trades),
            "mdd": max_drawdown * 100,
            "vsBH": total_return - buy_hold_return,
        },
    }
