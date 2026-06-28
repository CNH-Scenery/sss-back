from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, func, select

from app.db import get_session, seed_anonymous_user
from app.models import Scenario, UserResponse
from app.schemas import UserResponseCreate, UserResponseItem, UserResponseListResponse, UserResponseWriteResponse
from app.seed import seed_static_scenarios

router = APIRouter(prefix="/responses", tags=["Response API"])


def _response_count(session: Session, user_id) -> int:
    statement = select(func.count()).select_from(UserResponse).where(UserResponse.user_id == user_id)
    return int(session.exec(statement).one())


@router.post("", response_model=UserResponseWriteResponse)
def create_response(
    payload: UserResponseCreate,
    session: Session = Depends(get_session),
) -> UserResponseWriteResponse:
    user = seed_anonymous_user(session)
    seed_static_scenarios(session)
    scenario = session.get(Scenario, payload.scenario_id)
    if scenario is None:
        raise HTTPException(status_code=404, detail="Scenario not found")

    existing = session.exec(
        select(UserResponse).where(
            UserResponse.user_id == user.id,
            UserResponse.scenario_id == payload.scenario_id,
        )
    ).first()

    if existing:
        existing.decision = payload.decision.value
        existing.natural_reason = payload.natural_reason
        existing.confidence = payload.confidence
        existing.preferred_action = payload.preferred_action
        response = existing
    else:
        response = UserResponse(
            user_id=user.id,
            scenario_id=payload.scenario_id,
            decision=payload.decision.value,
            natural_reason=payload.natural_reason,
            confidence=payload.confidence,
            preferred_action=payload.preferred_action,
        )
        session.add(response)

    session.commit()
    session.refresh(response)
    count = _response_count(session, user.id)
    return UserResponseWriteResponse(
        response_id=str(response.id),
        response_count=count,
        can_generate_twin=count >= 10,
    )


@router.get("/me", response_model=UserResponseListResponse)
def list_my_responses(session: Session = Depends(get_session)) -> UserResponseListResponse:
    user = seed_anonymous_user(session)
    responses = session.exec(
        select(UserResponse)
        .where(UserResponse.user_id == user.id)
        .order_by(UserResponse.created_at, UserResponse.id)
    ).all()
    return UserResponseListResponse(
        response_count=len(responses),
        can_generate_twin=len(responses) >= 10,
        items=[
            UserResponseItem(
                id=str(response.id),
                scenario_id=str(response.scenario_id),
                decision=response.decision,
                natural_reason=response.natural_reason,
                confidence=response.confidence,
                preferred_action=response.preferred_action,
            )
            for response in responses
        ],
    )
