from fastapi import APIRouter

from app.schemas import MessageResponse, UserResponseCreate

router = APIRouter(prefix="/responses", tags=["Response API"])


@router.post("", response_model=MessageResponse)
def create_response(payload: UserResponseCreate) -> MessageResponse:
    return MessageResponse(message=f"response contract accepted for {payload.scenario_id}")


@router.get("/me", response_model=MessageResponse)
def list_my_responses() -> MessageResponse:
    return MessageResponse(message="response list contract")
