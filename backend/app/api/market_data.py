from fastapi import APIRouter, Depends, HTTPException, Query

from app.schemas import MarketCandleResponse
from app.services.trading_runtime import TradingRuntime, normalize_market

router = APIRouter(prefix="/market", tags=["Market Data API"])


def get_trading_runtime() -> TradingRuntime:
    return TradingRuntime()


@router.get("/candles", response_model=MarketCandleResponse)
def get_candles(
    market: str = Query(default="KRW-BTC"),
    source: str = Query(default="daily"),
    count: int = Query(default=200, ge=1, le=200),
    unit: int = Query(default=1, ge=1, le=240),
    seconds: int = Query(default=200, ge=1, le=24 * 60 * 60),
    bucket_seconds: int = Query(default=1, ge=1, le=60),
    runtime: TradingRuntime = Depends(get_trading_runtime),
) -> MarketCandleResponse:
    normalized_market = normalize_market(market)
    try:
        candles = runtime.fetch_chart_candles(
            normalized_market,
            source,
            count=count,
            unit=unit,
            seconds=seconds,
            bucket_seconds=bucket_seconds,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return MarketCandleResponse(market=normalized_market, source=source, candles=candles)
