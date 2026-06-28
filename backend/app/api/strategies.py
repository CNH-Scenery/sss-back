from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import ValidationError
from sqlmodel import Session, func, select

from app.db import get_session, seed_anonymous_user
from app.models import TwinContext, TwinStrategy
from app.schemas import MessageResponse, StrategyGenerateRequest, StrategyGenerateResponse, StrategyJSON
from app.services.llm_service import LLMService
from app.services.strategy_validator import StrategyValidationError, StrategyValidator

router = APIRouter(prefix="/strategies", tags=["Strategy API"])


def get_llm_service() -> LLMService:
    return LLMService()


@router.post("/generate", response_model=StrategyGenerateResponse)
def generate_strategy(
    payload: StrategyGenerateRequest,
    session: Session = Depends(get_session),
    llm_service: LLMService = Depends(get_llm_service),
) -> StrategyGenerateResponse:
    user = seed_anonymous_user(session)
    twin_context = session.get(TwinContext, payload.context_id)
    if twin_context is None or twin_context.user_id != user.id:
        raise HTTPException(status_code=404, detail="TwinContext not found")

    raw_strategy = llm_service.generate_strategy(twin_context)
    try:
        strategy_json = StrategyJSON.model_validate(raw_strategy)
        StrategyValidator.validate(strategy_json)
    except (ValidationError, StrategyValidationError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    strategy = TwinStrategy(
        user_id=user.id,
        context_id=twin_context.id,
        version=_next_version(session, user.id),
        strategy_name=strategy_json.strategy_name,
        strategy_json=strategy_json.model_dump(mode="json"),
        status="validated",
    )
    session.add(strategy)
    session.commit()
    session.refresh(strategy)
    return _to_response(strategy)


@router.get("/latest", response_model=StrategyGenerateResponse)
def get_latest_strategy(session: Session = Depends(get_session)) -> StrategyGenerateResponse:
    user = seed_anonymous_user(session)
    strategy = session.exec(
        select(TwinStrategy)
        .where(TwinStrategy.user_id == user.id)
        .order_by(TwinStrategy.version.desc(), TwinStrategy.created_at.desc())
    ).first()
    if strategy is None:
        raise HTTPException(status_code=404, detail="Strategy not found")
    return _to_response(strategy)


@router.post("/{strategy_id}/regenerate", response_model=MessageResponse)
def regenerate_strategy(strategy_id: UUID) -> MessageResponse:
    return MessageResponse(message=f"regenerate contract accepted for {strategy_id}")


@router.post("/{strategy_id}/activate", response_model=MessageResponse)
def activate_strategy(strategy_id: UUID) -> MessageResponse:
    return MessageResponse(message=f"activate contract accepted for {strategy_id}")


def _next_version(session: Session, user_id) -> int:
    latest_version = session.exec(
        select(func.max(TwinStrategy.version)).where(TwinStrategy.user_id == user_id)
    ).one()
    return int(latest_version or 0) + 1


def _to_response(strategy: TwinStrategy) -> StrategyGenerateResponse:
    return StrategyGenerateResponse(
        strategy_id=str(strategy.id),
        version=strategy.version,
        strategy_name=strategy.strategy_name,
        entry_threshold=strategy.strategy_json.get("entry_threshold"),
        summary=strategy.strategy_json.get("summary", ""),
    )
