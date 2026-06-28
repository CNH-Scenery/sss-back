import asyncio
import json
from pathlib import Path
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, StreamingResponse
from sqlmodel import Session, select

from app.db import get_session, seed_anonymous_user
from app.models import GeneratedTradingCode, TradingCodeRun
from app.schemas import CodeGenerateRequest, CodeGenerateResponse, TradingCodeRunResponse
from app.services import backtester
from app.services.code_harness import CodeHarness
from app.services.code_runner import RunOutcome, run_once
from app.services.feature_engine import FeatureEngine

router = APIRouter(prefix="/trading-code", tags=["TradingCode API"])

# Streaming cadence bounds (seconds). 15m candles only change every 15 min, and Upbit
# rate-limits public endpoints, so default to 15s and clamp to a sane range.
STREAM_INTERVAL_DEFAULT = 15
STREAM_INTERVAL_MIN = 1
STREAM_INTERVAL_MAX = 3600

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


# --- Live monitoring: compute features now, run decide(), get a BUY/SELL/HOLD --------

_LIVE_LOOKBACK = 150
_SEVERITY = {"BUY": "info", "SELL": "warning", "HOLD": "info"}


def compute_features(market: str, timeframe: str) -> dict:
    """Latest-bar features for a market (overridable in tests)."""
    candles = backtester.fetch_candles(market=market, timeframe=timeframe, lookback=_LIVE_LOOKBACK)
    return FeatureEngine.latest_features(candles)


def _load_owned(session: Session, code_id: UUID) -> GeneratedTradingCode:
    user = seed_anonymous_user(session)
    record = session.get(GeneratedTradingCode, code_id)
    if record is None or record.user_id != user.id:
        raise HTTPException(status_code=404, detail="Generated trading code not found")
    return record


def _evaluate_live(code: str, market: str, timeframe: str) -> tuple[RunOutcome, float | None]:
    features = compute_features(market, timeframe)
    outcome = run_once(code, features, position=None)
    return outcome, features.get("close")


def _persist_run(session: Session, code_id: UUID, user_id: UUID, outcome: RunOutcome) -> TradingCodeRun:
    decision = outcome.decision or {}
    run = TradingCodeRun(
        code_id=code_id,
        user_id=user_id,
        status=outcome.status,
        decision=decision.get("action"),
        stdout=(decision.get("reason") or "")[:4000],
        error=outcome.error,
    )
    session.add(run)
    session.commit()
    session.refresh(run)
    return run


def _run_to_response(run: TradingCodeRun) -> TradingCodeRunResponse:
    return TradingCodeRunResponse(
        run_id=str(run.id),
        code_id=str(run.code_id),
        status=run.status,
        decision=run.decision,
        error=run.error,
        executed_at=run.executed_at,
    )


@router.post("/{code_id}/run", response_model=TradingCodeRunResponse)
def run_trading_code(
    code_id: UUID,
    market: str = "KRW-BTC",
    timeframe: str = "15m",
    session: Session = Depends(get_session),
) -> TradingCodeRunResponse:
    """Compute the latest features for `market` and run decide() once (BUY/SELL/HOLD)."""
    record = _load_owned(session, code_id)
    if record.status != "passed":
        raise HTTPException(status_code=409, detail="code did not pass verification and cannot be run")
    outcome, _ = _evaluate_live(record.code, market, timeframe)
    run = _persist_run(session, record.id, record.user_id, outcome)
    return _run_to_response(run)


@router.get("/{code_id}/runs", response_model=list[TradingCodeRunResponse])
def list_trading_code_runs(
    code_id: UUID, limit: int = 20, session: Session = Depends(get_session)
) -> list[TradingCodeRunResponse]:
    record = _load_owned(session, code_id)
    runs = session.exec(
        select(TradingCodeRun)
        .where(TradingCodeRun.code_id == record.id)
        .order_by(TradingCodeRun.executed_at.desc())
        .limit(limit)
    ).all()
    return [_run_to_response(run) for run in runs]


@router.websocket("/{code_id}/stream")
async def stream_trading_code(
    websocket: WebSocket, code_id: UUID, session: Session = Depends(get_session)
) -> None:
    """Real-time monitor: every `interval`s, compute features -> decide() -> push an
    alert message {type:"alert", action, market, price, reason, severity, ts, decision}.
    Query params: market (KRW-BTC), timeframe (15m), interval (seconds, default 15).
    """
    await websocket.accept()
    try:
        record = _load_owned(session, code_id)
    except HTTPException as exc:
        await websocket.send_json({"type": "error", "error": exc.detail})
        await websocket.close()
        return
    if record.status != "passed":
        await websocket.send_json({"type": "error", "error": "code did not pass verification and cannot be run"})
        await websocket.close()
        return

    qp = websocket.query_params
    market = qp.get("market", "KRW-BTC")
    timeframe = qp.get("timeframe", "15m")
    try:
        interval = max(STREAM_INTERVAL_MIN, min(STREAM_INTERVAL_MAX, int(float(qp.get("interval", STREAM_INTERVAL_DEFAULT)))))
    except ValueError:
        interval = STREAM_INTERVAL_DEFAULT

    code, rec_id, user_id = record.code, record.id, record.user_id
    try:
        while True:
            outcome, price = await asyncio.to_thread(_evaluate_live, code, market, timeframe)
            run = _persist_run(session, rec_id, user_id, outcome)
            decision = outcome.decision or {}
            action = decision.get("action") or ("ERROR" if outcome.status == "error" else "HOLD")
            await websocket.send_json({
                "type": "alert",
                "action": action,
                "market": market,
                "price": price,
                "reason": decision.get("reason") or outcome.error or "",
                "severity": _SEVERITY.get(action, "info"),
                "ts": int(run.executed_at.timestamp() * 1000),
                "run_id": str(run.id),
                "status": outcome.status,
                "decision": decision or None,
            })
            await asyncio.sleep(interval)
    except WebSocketDisconnect:
        return
