from fastapi import APIRouter

from app.schemas import FeedbackCreate, MessageResponse

router = APIRouter(prefix="/feedbacks", tags=["Feedback API"])


@router.post("", response_model=MessageResponse)
def create_feedback(payload: FeedbackCreate) -> MessageResponse:
    return MessageResponse(message=f"feedback contract accepted for {payload.target_id}")
