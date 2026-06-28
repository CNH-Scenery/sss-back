from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session

from app.db import get_session, seed_anonymous_user
from app.models import CodeBacktestRun, GeneratedTradingCode
from app.schemas import BacktestMetrics, BacktestResultResponse, CodeBacktestRequest
from app.services import backtester

router = APIRouter(prefix="/backtests", tags=["Backtest API"])


@router.post("/run", response_model=BacktestResultResponse)
def run_backtest(
    payload: CodeBacktestRequest, session: Session = Depends(get_session)
) -> BacktestResultResponse:
    user = seed_anonymous_user(session)
    code_record = session.get(GeneratedTradingCode, payload.code_id)
    if code_record is None or code_record.user_id != user.id:
        raise HTTPException(status_code=404, detail="Generated trading code not found")
    if code_record.status != "passed":
        raise HTTPException(status_code=409, detail="code did not pass verification and cannot be backtested")

    candles = backtester.fetch_candles(
        market=payload.market,
        timeframe=payload.timeframe,
        lookback=payload.lookback,
        start=payload.start,
        end=payload.end,
    )
    result = backtester.run_backtest(code_record.code, candles, payload.initial_cash)
    if "engine_error" in result:
        raise HTTPException(status_code=422, detail=f"backtest failed: {result['engine_error']}")

    bt = result["backtest"]
    period_start = candles[0]["candle_time"] if candles else payload.start
    period_end = candles[-1]["candle_time"] if candles else payload.end

    record = CodeBacktestRun(
        user_id=user.id,
        code_id=code_record.id,
        market=payload.market,
        timeframe=payload.timeframe,
        period_start=period_start,
        period_end=period_end,
        initial_cash=payload.initial_cash,
        metrics_json=bt["metrics"],
        result_json={
            "eq": bt["eq"],
            "bh": bt["bh"],
            "candles": bt["candles"],
            "markers": bt["markers"],
            "trades": bt["trades"],
        },
    )
    session.add(record)
    session.commit()
    session.refresh(record)
    return _to_response(record)


@router.get("/{backtest_run_id}", response_model=BacktestResultResponse)
def get_backtest(backtest_run_id: UUID, session: Session = Depends(get_session)) -> BacktestResultResponse:
    user = seed_anonymous_user(session)
    record = session.get(CodeBacktestRun, backtest_run_id)
    if record is None or record.user_id != user.id:
        raise HTTPException(status_code=404, detail="Backtest run not found")
    return _to_response(record)


def _to_response(record: CodeBacktestRun) -> BacktestResultResponse:
    result = record.result_json or {}
    return BacktestResultResponse(
        backtest_run_id=str(record.id),
        code_id=str(record.code_id),
        market=record.market,
        timeframe=record.timeframe,
        period_start=record.period_start,
        period_end=record.period_end,
        metrics=BacktestMetrics(**record.metrics_json),
        eq=result.get("eq", []),
        bh=result.get("bh", []),
        candles=result.get("candles", []),
        markers=result.get("markers", []),
    )
