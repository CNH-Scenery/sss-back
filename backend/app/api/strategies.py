from uuid import UUID

from fastapi import APIRouter

from app.schemas import MessageResponse, StrategyGenerateRequest, StrategyGenerateResponse

router = APIRouter(prefix="/strategies", tags=["Strategy API"])


@router.post("/generate", response_model=StrategyGenerateResponse)
def generate_strategy(payload: StrategyGenerateRequest) -> StrategyGenerateResponse:
    return StrategyGenerateResponse(summary=f"strategy contract accepted for {payload.context_id}")


@router.get("/latest", response_model=StrategyGenerateResponse)
def get_latest_strategy() -> StrategyGenerateResponse:
    return StrategyGenerateResponse(summary="latest strategy contract")


@router.post("/{strategy_id}/regenerate", response_model=MessageResponse)
def regenerate_strategy(strategy_id: UUID) -> MessageResponse:
    return MessageResponse(message=f"regenerate contract accepted for {strategy_id}")


@router.post("/{strategy_id}/activate", response_model=MessageResponse)
def activate_strategy(strategy_id: UUID) -> MessageResponse:
    return MessageResponse(message=f"activate contract accepted for {strategy_id}")
