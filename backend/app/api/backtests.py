from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException

from app.schemas import BacktestRunRequest, BacktestRunResponse, MessageResponse
from app.services.trading_runtime import TradingRuntime

router = APIRouter(prefix="/backtests", tags=["Backtest API"])


def get_trading_runtime() -> TradingRuntime:
    return TradingRuntime()


@router.post("/run", response_model=BacktestRunResponse)
def run_backtest(
    payload: BacktestRunRequest,
    runtime: TradingRuntime = Depends(get_trading_runtime),
) -> BacktestRunResponse:
    try:
        result = runtime.run_backtest(
            market=payload.market,
            start_date=payload.period_start,
            end_date=payload.period_end,
            strategy_params=payload.strategy_params.model_dump(),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return BacktestRunResponse.model_validate(result)


@router.get("/{backtest_run_id}", response_model=MessageResponse)
def get_backtest(backtest_run_id: UUID) -> MessageResponse:
    return MessageResponse(message=f"backtest contract accepted for {backtest_run_id}")
