"""Executes a stored trading-code script and reports its decision.

Reuses the verifier's sandboxed runner (static allowlist + isolated subprocess) so
running stored code is held to the same safety bar as generation. The decision is the
buy/reject token the script prints to stdout.
"""
from dataclasses import dataclass

from app.services.code_verifier import verify


@dataclass
class RunOutcome:
    status: str  # "ok" | "error"
    decision: str | None  # "buy" | "reject" when status == "ok"
    error: str | None
    stdout: str


def run_once(code: str) -> RunOutcome:
    report = verify(code)
    if report.passed:
        decision = (report.decision_sample or {}).get("action")
        return RunOutcome(status="ok", decision=decision, error=None, stdout=report.stdout)

    detail = "; ".join(report.errors) if report.errors else report.stage
    return RunOutcome(status="error", decision=None, error=f"[{report.stage}] {detail}", stdout=report.stdout)
