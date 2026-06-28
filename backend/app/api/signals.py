from uuid import UUID

from fastapi import APIRouter

from app.schemas import MessageResponse, SignalListResponse

router = APIRouter(prefix="/signals", tags=["Signal API"])


@router.get("", response_model=SignalListResponse)
def list_signals() -> SignalListResponse:
    return SignalListResponse(items=[])


@router.post("/{signal_id}/approve", response_model=MessageResponse)
def approve_signal(signal_id: UUID) -> MessageResponse:
    return MessageResponse(message=f"approve contract accepted for {signal_id}")


@router.post("/{signal_id}/reject", response_model=MessageResponse)
def reject_signal(signal_id: UUID) -> MessageResponse:
    return MessageResponse(message=f"reject contract accepted for {signal_id}")


@router.post("/{signal_id}/mark-not-me", response_model=MessageResponse)
def mark_signal_not_me(signal_id: UUID) -> MessageResponse:
    return MessageResponse(message=f"mark-not-me contract accepted for {signal_id}")
