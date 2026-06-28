from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from sqlmodel import Session, select

from app.models import CandleCache

TIMEFRAME_TO_UNIT = {"15m": 15, "60m": 60}


class CandleCacheService:
    @staticmethod
    def get_or_fetch_minutes(
        session: Session,
        client,
        market: str,
        timeframe: str,
        count: int,
        to: str | None = None,
    ) -> list[CandleCache]:
        if timeframe not in TIMEFRAME_TO_UNIT:
            raise ValueError("Only 15m and 60m timeframes are supported")

        if to is not None:
            cached = CandleCacheService._cached_range(session, market, timeframe, count, to)
            if len(cached) == count:
                return cached

        rows = client.list_minute_candles(
            market=market,
            unit=TIMEFRAME_TO_UNIT[timeframe],
            count=count,
            to=to,
        )
        for row in sorted(rows, key=lambda item: item["candle_time"]):
            CandleCacheService._insert_if_missing(session, row)
        session.commit()

        refreshed = CandleCacheService._cached_range(session, market, timeframe, count, to)
        if len(refreshed) >= count:
            return refreshed
        return CandleCacheService._rows_from_payload(session, rows)

    @staticmethod
    def _cached_range(
        session: Session,
        market: str,
        timeframe: str,
        count: int,
        to: str | None,
    ) -> list[CandleCache]:
        statement = (
            select(CandleCache)
            .where(CandleCache.market == market, CandleCache.timeframe == timeframe)
            .order_by(CandleCache.candle_time.desc())
            .limit(count)
        )
        if to:
            statement = statement.where(CandleCache.candle_time < _parse_datetime(to))

        rows = session.exec(statement).all()
        return list(reversed(rows))

    @staticmethod
    def _insert_if_missing(session: Session, row: dict[str, Any]) -> None:
        candle_time = _parse_datetime(str(row["candle_time"]))
        existing = session.exec(
            select(CandleCache).where(
                CandleCache.market == row["market"],
                CandleCache.timeframe == row["timeframe"],
                CandleCache.candle_time == candle_time,
            )
        ).first()
        if existing is not None:
            return

        session.add(
            CandleCache(
                market=str(row["market"]),
                timeframe=str(row["timeframe"]),
                candle_time=candle_time,
                open=_decimal(row["open"]),
                high=_decimal(row["high"]),
                low=_decimal(row["low"]),
                close=_decimal(row["close"]),
                volume=_decimal(row["volume"]),
                trade_price=_decimal(row["trade_price"]),
            )
        )

    @staticmethod
    def _rows_from_payload(session: Session, rows: list[dict[str, Any]]) -> list[CandleCache]:
        candle_times = [_parse_datetime(str(row["candle_time"])) for row in rows]
        if not candle_times:
            return []
        market = str(rows[0]["market"])
        timeframe = str(rows[0]["timeframe"])
        return session.exec(
            select(CandleCache)
            .where(
                CandleCache.market == market,
                CandleCache.timeframe == timeframe,
                CandleCache.candle_time.in_(candle_times),
            )
            .order_by(CandleCache.candle_time)
        ).all()


def _parse_datetime(value: str) -> datetime:
    normalized = value.replace("Z", "+00:00")
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
        return parsed
    return parsed.astimezone(timezone.utc).replace(tzinfo=None)


def _decimal(value: Any) -> Decimal:
    return Decimal(str(value))
