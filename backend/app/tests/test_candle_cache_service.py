from collections.abc import Generator
import pytest
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, create_engine, select

from app.db import create_db_and_tables
from app.models import CandleCache
from app.services.candle_cache_service import CandleCacheService


@pytest.fixture()
def session() -> Generator[Session, None, None]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    create_db_and_tables(engine)
    with Session(engine) as db_session:
        yield db_session


class FakeUpbitClient:
    def __init__(self) -> None:
        self.calls = 0

    def list_minute_candles(self, market: str, unit: int, count: int, to: str | None = None):
        self.calls += 1
        assert market == "KRW-BTC"
        assert unit == 15
        assert count == 2
        return [
            {
                "market": "KRW-BTC",
                "timeframe": "15m",
                "candle_time": "2026-06-28T03:15:00+00:00",
                "open": 101.0,
                "high": 106.0,
                "low": 99.0,
                "close": 104.0,
                "volume": 11.0,
                "trade_price": 1144.0,
            },
            {
                "market": "KRW-BTC",
                "timeframe": "15m",
                "candle_time": "2026-06-28T03:00:00+00:00",
                "open": 100.0,
                "high": 105.0,
                "low": 98.0,
                "close": 101.0,
                "volume": 10.0,
                "trade_price": 1010.0,
            },
        ]


def test_fetches_krw_btc_15m_candles_sorts_ascending_and_saves(session: Session):
    client = FakeUpbitClient()

    candles = CandleCacheService.get_or_fetch_minutes(
        session=session,
        client=client,
        market="KRW-BTC",
        timeframe="15m",
        count=2,
        to="2026-06-28T12:30:00+09:00",
    )

    assert client.calls == 1
    assert [candle.candle_time.isoformat() for candle in candles] == [
        "2026-06-28T03:00:00",
        "2026-06-28T03:15:00",
    ]
    saved = session.exec(select(CandleCache).order_by(CandleCache.candle_time)).all()
    assert len(saved) == 2
    assert [row.market for row in saved] == ["KRW-BTC", "KRW-BTC"]
    assert [row.timeframe for row in saved] == ["15m", "15m"]


def test_uses_cached_candles_for_same_period_without_calling_api(session: Session):
    client = FakeUpbitClient()

    first = CandleCacheService.get_or_fetch_minutes(
        session=session,
        client=client,
        market="KRW-BTC",
        timeframe="15m",
        count=2,
        to="2026-06-28T12:30:00+09:00",
    )
    second = CandleCacheService.get_or_fetch_minutes(
        session=session,
        client=client,
        market="KRW-BTC",
        timeframe="15m",
        count=2,
        to="2026-06-28T12:30:00+09:00",
    )

    assert client.calls == 1
    assert [candle.id for candle in second] == [candle.id for candle in first]


def test_latest_request_without_to_fetches_again(session: Session):
    client = FakeUpbitClient()

    CandleCacheService.get_or_fetch_minutes(
        session=session,
        client=client,
        market="KRW-BTC",
        timeframe="15m",
        count=2,
        to="2026-06-28T12:30:00+09:00",
    )
    CandleCacheService.get_or_fetch_minutes(
        session=session,
        client=client,
        market="KRW-BTC",
        timeframe="15m",
        count=2,
        to=None,
    )

    assert client.calls == 2


def test_supports_60m_timeframe_mapping(session: Session):
    class SixtyMinuteClient:
        def list_minute_candles(self, market: str, unit: int, count: int, to: str | None = None):
            assert unit == 60
            return [
                {
                    "market": market,
                    "timeframe": "60m",
                    "candle_time": "2026-06-28T03:00:00+00:00",
                    "open": 100.0,
                    "high": 105.0,
                    "low": 98.0,
                    "close": 101.0,
                    "volume": 10.0,
                    "trade_price": 1010.0,
                }
            ]

    candles = CandleCacheService.get_or_fetch_minutes(
        session=session,
        client=SixtyMinuteClient(),
        market="KRW-BTC",
        timeframe="60m",
        count=1,
        to="2026-06-28T13:00:00+09:00",
    )

    assert len(candles) == 1
    assert candles[0].timeframe == "60m"


def test_rejects_unsupported_timeframe(session: Session):
    with pytest.raises(ValueError, match="Only 15m and 60m"):
        CandleCacheService.get_or_fetch_minutes(
            session=session,
            client=FakeUpbitClient(),
            market="KRW-BTC",
            timeframe="30m",
            count=1,
            to="2026-06-28T12:30:00+09:00",
        )
