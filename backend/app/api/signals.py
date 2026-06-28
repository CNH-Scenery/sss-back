from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException

from app.schemas import MessageResponse, MonitorRunRequest, MonitorRunResponse, SignalListResponse
from app.services.trading_runtime import TradingRuntime

router = APIRouter(prefix="/signals", tags=["Signal API"])


def get_trading_runtime() -> TradingRuntime:
    return TradingRuntime()


@router.get("", response_model=SignalListResponse)
def list_signals() -> SignalListResponse:
    return SignalListResponse(items=[])


@router.post("/monitor", response_model=MonitorRunResponse)
def monitor_signal(
    payload: MonitorRunRequest,
    runtime: TradingRuntime = Depends(get_trading_runtime),
) -> MonitorRunResponse:
    try:
        result = runtime.evaluate_monitor(
            market=payload.market,
            strategy_params=payload.strategy_params.model_dump(),
            position=payload.position.model_dump(),
            unit=payload.unit,
            count=payload.count,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return MonitorRunResponse.model_validate(result)


@router.post("/{signal_id}/approve", response_model=MessageResponse)
def approve_signal(signal_id: UUID) -> MessageResponse:
    return MessageResponse(message=f"approve contract accepted for {signal_id}")


@router.post("/{signal_id}/reject", response_model=MessageResponse)
def reject_signal(signal_id: UUID) -> MessageResponse:
    return MessageResponse(message=f"reject contract accepted for {signal_id}")


@router.post("/{signal_id}/mark-not-me", response_model=MessageResponse)
def mark_signal_not_me(signal_id: UUID) -> MessageResponse:
    return MessageResponse(message=f"mark-not-me contract accepted for {signal_id}")
