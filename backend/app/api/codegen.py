from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from app.db import get_session, seed_anonymous_user
from app.models import GeneratedTradingCode
from app.schemas import CodeGenerateRequest, CodeGenerateResponse
from app.services.code_harness import CodeHarness

router = APIRouter(prefix="/trading-code", tags=["TradingCode API"])


def get_harness() -> CodeHarness:
    return CodeHarness()


@router.post("/generate", response_model=CodeGenerateResponse)
def generate_trading_code(
    payload: CodeGenerateRequest,
    session: Session = Depends(get_session),
    harness: CodeHarness = Depends(get_harness),
) -> CodeGenerateResponse:
    user = seed_anonymous_user(session)
    result = harness.run(
        prompt=payload.prompt,
        market=payload.market,
        timeframe=payload.timeframe,
        max_iterations=payload.max_iterations,
    )

    record = GeneratedTradingCode(
        user_id=user.id,
        prompt=payload.prompt,
        market=payload.market,
        timeframe=payload.timeframe,
        code=result.code,
        status="passed" if result.passed else "failed",
        iterations=result.iterations,
        model_name=result.model_name,
        verification_json=result.report.to_dict(),
    )
    session.add(record)
    session.commit()
    session.refresh(record)
    return _to_response(record, result.report.decision_sample)


@router.get("/latest", response_model=CodeGenerateResponse)
def get_latest_trading_code(session: Session = Depends(get_session)) -> CodeGenerateResponse:
    user = seed_anonymous_user(session)
    record = session.exec(
        select(GeneratedTradingCode)
        .where(GeneratedTradingCode.user_id == user.id)
        .order_by(GeneratedTradingCode.created_at.desc())
    ).first()
    if record is None:
        raise HTTPException(status_code=404, detail="No generated trading code found")
    return _to_response(record)


@router.get("/{code_id}", response_model=CodeGenerateResponse)
def get_trading_code(code_id: UUID, session: Session = Depends(get_session)) -> CodeGenerateResponse:
    user = seed_anonymous_user(session)
    record = session.get(GeneratedTradingCode, code_id)
    if record is None or record.user_id != user.id:
        raise HTTPException(status_code=404, detail="Generated trading code not found")
    return _to_response(record)


def _to_response(record: GeneratedTradingCode, decision_sample=None) -> CodeGenerateResponse:
    return CodeGenerateResponse(
        code_id=str(record.id),
        status=record.status,
        passed=record.status == "passed",
        iterations=record.iterations,
        model_name=record.model_name,
        code=record.code,
        verification=record.verification_json,
        decision_sample=decision_sample,
    )
