"""Self-correcting code-generation loop.

Asks Claude for a trading script, verifies it, and on failure feeds the verification
errors back as a new turn so Claude can fix them. Repeats up to max_iterations.
"""
import os
from collections.abc import Iterator
from dataclasses import dataclass
from typing import Any

from app.services.anthropic_client import AnthropicCodeClient
from app.services.code_contract import build_retry_prompt, build_user_prompt
from app.services.code_verifier import VerificationReport, verify

DEFAULT_MAX_ITERATIONS = 4


def default_max_iterations() -> int:
    try:
        return max(1, int(os.getenv("CODEGEN_MAX_ITERATIONS", str(DEFAULT_MAX_ITERATIONS))))
    except ValueError:
        return DEFAULT_MAX_ITERATIONS


@dataclass
class HarnessResult:
    passed: bool
    iterations: int
    code: str
    report: VerificationReport
    model_name: str


class CodeHarness:
    def __init__(self, client: AnthropicCodeClient | None = None) -> None:
        self.client = client or AnthropicCodeClient()

    def run(self, prompt: str, max_iterations: int | None = None) -> HarnessResult:
        limit = max_iterations or default_max_iterations()
        history: list[dict[str, Any]] = [{"role": "user", "content": build_user_prompt(prompt)}]

        code = ""
        report = VerificationReport(False, "static", ["no code generated"])
        for attempt in range(1, limit + 1):
            code = self.client.generate_code(history)
            report = verify(code)
            if report.passed:
                return HarnessResult(True, attempt, code, report, self.client.model_name)

            # Feed the failure back so the next attempt can fix it.
            history.append({"role": "assistant", "content": f"```python\n{code}\n```"})
            history.append(
                {"role": "user", "content": build_retry_prompt(report.errors, report.stage)}
            )

        return HarnessResult(False, limit, code, report, self.client.model_name)

    def stream(self, prompt: str, max_iterations: int | None = None) -> Iterator[dict[str, Any]]:
        """Same loop as run(), but yields one event per step so callers can render
        each iteration (generate → verify → retry) as it happens."""
        limit = max_iterations or default_max_iterations()
        model_name = self.client.model_name
        history: list[dict[str, Any]] = [{"role": "user", "content": build_user_prompt(prompt)}]
        yield {"event": "start", "limit": limit, "model_name": model_name, "prompt": prompt}

        code = ""
        report = VerificationReport(False, "static", ["no code generated"])
        for attempt in range(1, limit + 1):
            yield {"event": "attempt_start", "attempt": attempt, "limit": limit}

            try:
                code = self.client.generate_code(history)
            except Exception as exc:  # noqa: BLE001 - surface generation failure to the client
                yield {"event": "error", "attempt": attempt, "message": f"{type(exc).__name__}: {exc}"}
                yield {
                    "event": "done",
                    "passed": False,
                    "iterations": attempt,
                    "code": code,
                    "report": report.to_dict(),
                    "decision_sample": None,
                    "model_name": model_name,
                }
                return

            yield {"event": "generated", "attempt": attempt, "code": code}

            report = verify(code)
            yield {
                "event": "verified",
                "attempt": attempt,
                "passed": report.passed,
                "stage": report.stage,
                "errors": report.errors,
                "stdout": report.stdout[:4000],
                "decision_sample": report.decision_sample,
            }

            if report.passed:
                yield {
                    "event": "done",
                    "passed": True,
                    "iterations": attempt,
                    "code": code,
                    "report": report.to_dict(),
                    "decision_sample": report.decision_sample,
                    "model_name": model_name,
                }
                return

            history.append({"role": "assistant", "content": f"```python\n{code}\n```"})
            history.append(
                {"role": "user", "content": build_retry_prompt(report.errors, report.stage)}
            )
            yield {"event": "retry", "attempt": attempt, "stage": report.stage, "errors": report.errors}

        yield {
            "event": "done",
            "passed": False,
            "iterations": limit,
            "code": code,
            "report": report.to_dict(),
            "decision_sample": report.decision_sample,
            "model_name": model_name,
        }
