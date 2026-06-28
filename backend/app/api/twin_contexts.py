from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import ValidationError
from sqlmodel import Session, func, select

from app.db import get_session, seed_anonymous_user
from app.models import Scenario, TwinContext, UserResponse
from app.schemas import TwinContextGenerateResponse, TwinContextSchema
from app.services.llm_service import LLMService

router = APIRouter(prefix="/twin-contexts", tags=["TwinContext API"])


def get_llm_service() -> LLMService:
    return LLMService()


@router.post("/generate", response_model=TwinContextGenerateResponse)
def generate_twin_context(
    session: Session = Depends(get_session),
    llm_service: LLMService = Depends(get_llm_service),
) -> TwinContextGenerateResponse:
    user = seed_anonymous_user(session)
    responses = _user_responses(session, user.id)
    if len(responses) < 10:
        raise HTTPException(status_code=400, detail="TwinContext generation requires at least 10 responses")

    raw_context = llm_service.analyze_user_responses(_response_bundle(session, responses))
    try:
        validated_context = TwinContextSchema.model_validate(raw_context)
    except ValidationError as exc:
        raise HTTPException(status_code=502, detail="TwinContext schema validation failed") from exc

    context = TwinContext(
        user_id=user.id,
        version=_next_version(session, user.id),
        source_response_ids=[str(response.id) for response in responses],
        style_summary=validated_context.style_summary,
        context_json={
            "important_signals": validated_context.important_signals,
            "avoid_conditions": validated_context.avoid_conditions,
            "decision_profile": validated_context.decision_profile,
            "confidence_profile": validated_context.confidence_profile,
        },
        uncertainty_json={"items": validated_context.uncertainty},
    )
    session.add(context)
    session.commit()
    session.refresh(context)
    return _to_response(context)


@router.get("/latest", response_model=TwinContextGenerateResponse)
def get_latest_twin_context(session: Session = Depends(get_session)) -> TwinContextGenerateResponse:
    user = seed_anonymous_user(session)
    context = session.exec(
        select(TwinContext)
        .where(TwinContext.user_id == user.id)
        .order_by(TwinContext.version.desc(), TwinContext.created_at.desc())
    ).first()
    if context is None:
        raise HTTPException(status_code=404, detail="TwinContext not found")
    return _to_response(context)


def _user_responses(session: Session, user_id) -> list[UserResponse]:
    return session.exec(
        select(UserResponse)
        .where(UserResponse.user_id == user_id)
        .order_by(UserResponse.created_at, UserResponse.id)
    ).all()


def _response_bundle(session: Session, responses: list[UserResponse]) -> list[dict[str, Any]]:
    bundled = []
    for response in responses:
        scenario = session.get(Scenario, response.scenario_id)
        if scenario is None:
            continue
        bundled.append(
            {
                "id": str(response.id),
                "decision": response.decision,
                "natural_reason": response.natural_reason,
                "confidence": response.confidence,
                "preferred_action": response.preferred_action,
                "scenario": {
                    "id": str(scenario.id),
                    "market": scenario.market,
                    "timeframe": scenario.timeframe,
                    "description": scenario.description,
                    "features_snapshot": scenario.features_snapshot,
                },
            }
        )
    return bundled


def _next_version(session: Session, user_id) -> int:
    latest_version = session.exec(
        select(func.max(TwinContext.version)).where(TwinContext.user_id == user_id)
    ).one()
    return int(latest_version or 0) + 1


def _to_response(context: TwinContext) -> TwinContextGenerateResponse:
    return TwinContextGenerateResponse(
        context_id=str(context.id),
        version=context.version,
        style_summary=context.style_summary,
        important_signals=context.context_json.get("important_signals", []),
        avoid_conditions=context.context_json.get("avoid_conditions", []),
        uncertainty=context.uncertainty_json.get("items", []),
    )
