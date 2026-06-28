"""Self-correcting code-generation loop.

Asks Claude for a trading module, verifies it, and on failure feeds the verification
errors back as a new turn so Claude can fix them. Repeats up to max_iterations.
"""
import os
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

    def run(
        self,
        prompt: str,
        market: str,
        timeframe: str,
        max_iterations: int | None = None,
    ) -> HarnessResult:
        limit = max_iterations or default_max_iterations()
        history: list[dict[str, Any]] = [
            {"role": "user", "content": build_user_prompt(prompt, market, timeframe)}
        ]

        code = ""
        report = VerificationReport(False, "static", ["no code generated"])
        for attempt in range(1, limit + 1):
            code = self.client.generate_code(history)
            report = verify(code, market, timeframe)
            if report.passed:
                return HarnessResult(True, attempt, code, report, self.client.model_name)

            # Feed the failure back so the next attempt can fix it.
            history.append({"role": "assistant", "content": f"```python\n{code}\n```"})
            history.append(
                {"role": "user", "content": build_retry_prompt(report.errors, report.stage)}
            )

        return HarnessResult(False, limit, code, report, self.client.model_name)
