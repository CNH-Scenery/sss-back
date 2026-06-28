import httpx
import pytest

from app.services.upbit_client import UpbitClient, UpbitRateLimitError, parse_remaining_req


def test_parse_remaining_req_extracts_group_min_and_sec():
    parsed = parse_remaining_req("group=market; min=600; sec=9")

    assert parsed == {"group": "market", "min": 600, "sec": 9}


def test_list_krw_markets_filters_non_krw_pairs():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/market/all"
        return httpx.Response(
            200,
            json=[
                {"market": "KRW-BTC", "korean_name": "비트코인"},
                {"market": "BTC-ETH", "korean_name": "이더리움"},
                {"market": "KRW-ETH", "korean_name": "이더리움"},
            ],
        )

    client = UpbitClient(http_client=httpx.Client(transport=httpx.MockTransport(handler)))

    assert client.list_krw_markets() == ["KRW-BTC", "KRW-ETH"]


def test_list_minute_candles_encodes_to_parameter_and_normalizes_fields():
    captured_urls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured_urls.append(str(request.url))
        return httpx.Response(
            200,
            headers={"Remaining-Req": "group=candles; min=600; sec=8"},
            json=[
                {
                    "market": "KRW-BTC",
                    "candle_date_time_utc": "2026-06-28T03:15:00",
                    "opening_price": 100.0,
                    "high_price": 110.0,
                    "low_price": 95.0,
                    "trade_price": 105.0,
                    "candle_acc_trade_volume": 12.5,
                    "candle_acc_trade_price": 1280.0,
                }
            ],
        )

    client = UpbitClient(http_client=httpx.Client(transport=httpx.MockTransport(handler)))
    candles = client.list_minute_candles(
        market="KRW-BTC",
        unit=15,
        count=1,
        to="2026-06-28T12:15:00+09:00",
    )

    assert "/v1/candles/minutes/15" in captured_urls[0]
    assert "to=2026-06-28T12%3A15%3A00%2B09%3A00" in captured_urls[0]
    assert candles == [
        {
            "market": "KRW-BTC",
            "timeframe": "15m",
            "candle_time": "2026-06-28T03:15:00+00:00",
            "open": 100.0,
            "high": 110.0,
            "low": 95.0,
            "close": 105.0,
            "volume": 12.5,
            "trade_price": 1280.0,
        }
    ]


def test_list_minute_candles_rejects_unsupported_unit():
    client = UpbitClient(http_client=httpx.Client(transport=httpx.MockTransport(lambda _: httpx.Response(200))))

    with pytest.raises(ValueError, match="Only 15m and 60m"):
        client.list_minute_candles(market="KRW-BTC", unit=30, count=1)


def test_rate_limit_response_raises_next_tick_retry_error():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(429, headers={"Remaining-Req": "group=candles; min=600; sec=0"})

    client = UpbitClient(http_client=httpx.Client(transport=httpx.MockTransport(handler)))

    with pytest.raises(UpbitRateLimitError) as exc_info:
        client.list_minute_candles(market="KRW-BTC", unit=15, count=1)

    assert exc_info.value.retry_after_seconds == 1
    assert exc_info.value.next_tick_retry is True
    assert exc_info.value.remaining_req == {"group": "candles", "min": 600, "sec": 0}
