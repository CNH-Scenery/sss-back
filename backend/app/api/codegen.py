import json
from pathlib import Path
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import HTMLResponse, StreamingResponse
from sqlmodel import Session, select

from app.db import get_session, seed_anonymous_user
from app.models import GeneratedTradingCode
from app.schemas import CodeGenerateRequest, CodeGenerateResponse
from app.services.code_harness import CodeHarness

router = APIRouter(prefix="/trading-code", tags=["TradingCode API"])

_PLAYGROUND_HTML = Path(__file__).resolve().parent.parent / "static" / "codegen_playground.html"


def get_harness() -> CodeHarness:
    return CodeHarness()


@router.post("/generate", response_model=CodeGenerateResponse)
def generate_trading_code(
    payload: CodeGenerateRequest,
    session: Session = Depends(get_session),
    harness: CodeHarness = Depends(get_harness),
) -> CodeGenerateResponse:
    user = seed_anonymous_user(session)
    result = harness.run(prompt=payload.prompt, max_iterations=payload.max_iterations)

    record = GeneratedTradingCode(
        user_id=user.id,
        prompt=payload.prompt,
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


@router.post("/generate/stream")
def generate_trading_code_stream(
    payload: CodeGenerateRequest,
    session: Session = Depends(get_session),
    harness: CodeHarness = Depends(get_harness),
) -> StreamingResponse:
    """Server-Sent Events variant of /generate: emits one event per loop step
    (start, attempt_start, generated, verified, retry, done) so a client can
    render each self-correction iteration live."""
    user = seed_anonymous_user(session)

    def event_stream():
        for ev in harness.stream(prompt=payload.prompt, max_iterations=payload.max_iterations):
            if ev.get("event") == "done":
                record = GeneratedTradingCode(
                    user_id=user.id,
                    prompt=payload.prompt,
                    code=ev["code"],
                    status="passed" if ev["passed"] else "failed",
                    iterations=ev["iterations"],
                    model_name=ev["model_name"],
                    verification_json=ev["report"],
                )
                session.add(record)
                session.commit()
                session.refresh(record)
                ev = {**ev, "code_id": str(record.id)}
            yield f"data: {json.dumps(ev, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/playground", response_class=HTMLResponse, include_in_schema=False)
def codegen_playground() -> HTMLResponse:
    """Serve the self-correction loop visualizer (same origin → no CORS)."""
    if not _PLAYGROUND_HTML.exists():
        raise HTTPException(status_code=404, detail="playground html not found")
    return HTMLResponse(_PLAYGROUND_HTML.read_text(encoding="utf-8"))


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
