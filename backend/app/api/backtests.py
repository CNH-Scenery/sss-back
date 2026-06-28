from uuid import UUID

from fastapi import APIRouter

from app.schemas import BacktestRunRequest, MessageResponse

router = APIRouter(prefix="/backtests", tags=["Backtest API"])


@router.post("/run", response_model=MessageResponse)
def run_backtest(payload: BacktestRunRequest) -> MessageResponse:
    return MessageResponse(message=f"backtest contract accepted for {payload.strategy_id}")


@router.get("/{backtest_run_id}", response_model=MessageResponse)
def get_backtest(backtest_run_id: UUID) -> MessageResponse:
    return MessageResponse(message=f"backtest contract accepted for {backtest_run_id}")
