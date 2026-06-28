from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

import httpx

SUPPORTED_MINUTE_UNITS = {15, 60}


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
            raise ValueError("Only 15m and 60m candles are supported")
        if count < 1 or count > 200:
            raise ValueError("count must be between 1 and 200")

        params: dict[str, str | int] = {"market": market, "count": count}
        if to:
            params["to"] = to

        response = self._get(f"/v1/candles/minutes/{unit}", params=params)
        return [self._normalize_candle(item, unit) for item in response.json()]

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

    def _normalize_candle(self, item: dict[str, Any], unit: int) -> dict[str, Any]:
        candle_time = datetime.fromisoformat(item["candle_date_time_utc"]).replace(
            tzinfo=timezone.utc
        )
        return {
            "market": item["market"],
            "timeframe": f"{unit}m",
            "candle_time": candle_time.isoformat(),
            "open": float(item["opening_price"]),
            "high": float(item["high_price"]),
            "low": float(item["low_price"]),
            "close": float(item["trade_price"]),
            "volume": float(item["candle_acc_trade_volume"]),
            "trade_price": float(item["candle_acc_trade_price"]),
        }
