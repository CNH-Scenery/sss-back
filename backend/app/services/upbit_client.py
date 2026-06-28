from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

import httpx

SUPPORTED_MINUTE_UNITS = {1, 3, 5, 10, 15, 30, 60, 240}


@dataclass
class UpbitRateLimitError(Exception):
    retry_after_seconds: int
    next_tick_retry: bool
    remaining_req: dict[str, str | int]


def parse_remaining_req(value: str | None) -> dict[str, str | int]:
    if not value:
        return {}

    parsed: dict[str, str | int] = {}
    for part in value.split(";"):
        if "=" not in part:
            continue
        key, raw_value = part.strip().split("=", 1)
        if key in {"min", "sec"}:
            parsed[key] = int(raw_value)
        else:
            parsed[key] = raw_value
    return parsed


class UpbitClient:
    def __init__(
        self,
        base_url: str = "https://api.upbit.com",
        http_client: httpx.Client | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.http_client = http_client or httpx.Client(base_url=self.base_url, timeout=10)

    def list_krw_markets(self) -> list[str]:
        response = self._get("/v1/market/all")
        return [
            item["market"]
            for item in response.json()
            if str(item.get("market", "")).startswith("KRW-")
        ]

    def list_minute_candles(
        self,
        market: str,
        unit: int,
        count: int,
        to: str | None = None,
    ) -> list[dict[str, Any]]:
        if unit not in SUPPORTED_MINUTE_UNITS:
            raise ValueError("unsupported minute candle unit")
        if count < 1 or count > 200:
            raise ValueError("count must be between 1 and 200")

        params: dict[str, str | int] = {"market": market, "count": count}
        if to:
            params["to"] = to

        response = self._get(f"/v1/candles/minutes/{unit}", params=params)
        return [self._normalize_candle(item, unit) for item in response.json()]

    def get_ticker(self, markets: list[str]) -> list[dict[str, Any]]:
        if not markets:
            raise ValueError("markets must not be empty")
        response = self._get("/v1/ticker", params={"markets": ",".join(markets)})
        return [
            {
                "market": item["market"],
                "trade_price": float(item["trade_price"]),
                "change": item.get("change"),
                "change_rate_24h": float(item.get("signed_change_rate", 0.0)),
                "high_price": float(item["high_price"]),
                "low_price": float(item["low_price"]),
                "acc_trade_price_24h": float(item.get("acc_trade_price_24h", 0.0)),
                "acc_trade_volume_24h": float(item.get("acc_trade_volume_24h", 0.0)),
            }
            for item in response.json()
        ]

    def get_orderbook(self, market: str, depth: int = 5) -> dict[str, Any]:
        response = self._get("/v1/orderbook", params={"markets": market})
        data = response.json()
        if not data:
            raise ValueError(f"no orderbook for {market}")
        book = data[0]
        units = book.get("orderbook_units", [])[: max(1, min(depth, 15))]
        return {
            "market": book["market"],
            "asks": [{"price": float(u["ask_price"]), "size": float(u["ask_size"])} for u in units],
            "bids": [{"price": float(u["bid_price"]), "size": float(u["bid_size"])} for u in units],
        }

    def list_daily_candles(
        self,
        market: str,
        count: int,
        to: str | None = None,
    ) -> list[dict[str, Any]]:
        if count < 1 or count > 200:
            raise ValueError("count must be between 1 and 200")
        params: dict[str, str | int] = {"market": market, "count": count}
        if to:
            params["to"] = to
        response = self._get("/v1/candles/days", params=params)
        return [self._normalize_period(item, "1d") for item in response.json()]

    def list_week_candles(
        self,
        market: str,
        count: int,
        to: str | None = None,
    ) -> list[dict[str, Any]]:
        return self._list_period_candles("weeks", "1w", market, count, to)

    def list_month_candles(
        self,
        market: str,
        count: int,
        to: str | None = None,
    ) -> list[dict[str, Any]]:
        return self._list_period_candles("months", "1mo", market, count, to)

    def list_year_candles(
        self,
        market: str,
        count: int,
        to: str | None = None,
    ) -> list[dict[str, Any]]:
        return self._list_period_candles("years", "1y", market, count, to)

    def list_second_candles(
        self,
        market: str,
        count: int,
        to: str | None = None,
    ) -> list[dict[str, Any]]:
        if count < 1 or count > 200:
            raise ValueError("count must be between 1 and 200")
        params: dict[str, str | int] = {"market": market, "count": count}
        if to:
            params["to"] = to
        response = self._get("/v1/candles/seconds", params=params)
        return [self._normalize_candle(item, 1, timeframe="1s") for item in response.json()]

    def _list_period_candles(
        self,
        endpoint: str,
        timeframe: str,
        market: str,
        count: int,
        to: str | None,
    ) -> list[dict[str, Any]]:
        if count < 1 or count > 200:
            raise ValueError("count must be between 1 and 200")
        params: dict[str, str | int] = {"market": market, "count": count}
        if to:
            params["to"] = to
        response = self._get(f"/v1/candles/{endpoint}", params=params)
        return [self._normalize_period(item, timeframe) for item in response.json()]

    def _normalize_period(self, item: dict[str, Any], timeframe: str) -> dict[str, Any]:
        candle_time = datetime.fromisoformat(item["candle_date_time_utc"]).replace(
            tzinfo=timezone.utc
        )
        return {
            "market": item["market"],
            "timeframe": timeframe,
            "candle_time": candle_time.isoformat(),
            "open": float(item["opening_price"]),
            "high": float(item["high_price"]),
            "low": float(item["low_price"]),
            "close": float(item["trade_price"]),
            "volume": float(item["candle_acc_trade_volume"]),
            "trade_price": float(item["candle_acc_trade_price"]),
        }

    def _get(self, path: str, params: dict[str, str | int] | None = None) -> httpx.Response:
        response = self.http_client.get(f"{self.base_url}{path}", params=params)
        if response.status_code == 429:
            raise UpbitRateLimitError(
                retry_after_seconds=1,
                next_tick_retry=True,
                remaining_req=parse_remaining_req(response.headers.get("Remaining-Req")),
            )
        response.raise_for_status()
        return response

    def _normalize_candle(
        self, item: dict[str, Any], unit: int, timeframe: str | None = None
    ) -> dict[str, Any]:
        candle_time = datetime.fromisoformat(item["candle_date_time_utc"]).replace(
            tzinfo=timezone.utc
        )
        return {
            "market": item["market"],
            "timeframe": timeframe or f"{unit}m",
            "candle_time": candle_time.isoformat(),
            "open": float(item["opening_price"]),
            "high": float(item["high_price"]),
            "low": float(item["low_price"]),
            "close": float(item["trade_price"]),
            "volume": float(item["candle_acc_trade_volume"]),
            "trade_price": float(item["candle_acc_trade_price"]),
        }
