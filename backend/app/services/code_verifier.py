"""Verifies LLM-generated trading code: static analysis + sandboxed execution.

Two stages:
  static_check  — parse the AST, enforce the import allowlist, and reject forbidden
                  symbols.
  runtime_check — run the script in an isolated subprocess (`python -I`) with a CPU
                  limit and wall-clock timeout, NO arguments, and confirm it prints
                  exactly one decision token ("buy" or "reject") to stdout.

Network access (httpx) is intentionally allowed per the data-access decision, so this
is robustness verification, not a full security sandbox.
"""
import ast
import os
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from app.services.code_contract import ALLOWED_IMPORTS, DECISIONS, FORBIDDEN_NAMES

RUNTIME_TIMEOUT_SECONDS = 20
CPU_LIMIT_SECONDS = 15


@dataclass
class VerificationReport:
    passed: bool
    stage: str  # "static" | "runtime" | "ok"
    errors: list[str] = field(default_factory=list)
    stdout: str = ""
    decision_sample: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "passed": self.passed,
            "stage": self.stage,
            "errors": self.errors,
            "stdout": self.stdout[:4000],
        }


def static_check(code: str) -> VerificationReport:
    errors: list[str] = []
    try:
        tree = ast.parse(code)
    except SyntaxError as exc:
        return VerificationReport(False, "static", [f"SyntaxError: {exc}"])

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                top = alias.name.split(".")[0]
                if top not in ALLOWED_IMPORTS:
                    errors.append(f"import '{alias.name}' is not in the allowlist")
        elif isinstance(node, ast.ImportFrom):
            top = (node.module or "").split(".")[0]
            if top not in ALLOWED_IMPORTS:
                errors.append(f"import from '{node.module}' is not in the allowlist")
        elif isinstance(node, ast.Name) and node.id in FORBIDDEN_NAMES:
            errors.append(f"forbidden name '{node.id}' is used")
        elif isinstance(node, ast.Attribute) and node.attr in FORBIDDEN_NAMES:
            errors.append(f"forbidden attribute '.{node.attr}' is used")

    # De-duplicate while preserving order.
    errors = list(dict.fromkeys(errors))
    return VerificationReport(passed=not errors, stage="static", errors=errors)


def _limit_resources() -> None:
    try:
        import resource

        resource.setrlimit(resource.RLIMIT_CPU, (CPU_LIMIT_SECONDS, CPU_LIMIT_SECONDS))
    except Exception:  # noqa: BLE001 - best effort; timeout is the hard backstop
        pass


def runtime_check(code: str) -> VerificationReport:
    """Run the script with no arguments and confirm it prints exactly buy/reject."""
    with tempfile.TemporaryDirectory() as tmp:
        strategy_path = Path(tmp) / "strategy_script.py"
        strategy_path.write_text(code, encoding="utf-8")
        subprocess_kwargs = {}
        if os.name != "nt":  # preexec_fn is POSIX-only
            subprocess_kwargs["preexec_fn"] = _limit_resources

        try:
            proc = subprocess.run(
                [sys.executable, "-I", str(strategy_path)],
                capture_output=True,
                text=True,
                timeout=RUNTIME_TIMEOUT_SECONDS,
                **subprocess_kwargs,
            )
        except subprocess.TimeoutExpired:
            return VerificationReport(
                False, "runtime", [f"execution exceeded {RUNTIME_TIMEOUT_SECONDS}s timeout"]
            )

        if proc.returncode != 0:
            return VerificationReport(
                False,
                "runtime",
                [f"process exited with code {proc.returncode}"],
                stdout=proc.stderr or proc.stdout,
            )

        decision = _last_token(proc.stdout)
        if decision not in DECISIONS:
            return VerificationReport(
                False,
                "runtime",
                [f"script must print exactly one of {list(DECISIONS)}; got: {decision!r}"],
                stdout=proc.stdout,
            )

        return VerificationReport(
            passed=True,
            stage="ok",
            decision_sample={"action": decision},
            stdout=proc.stdout,
        )


def _last_token(stdout: str) -> str | None:
    """The decision is the last non-empty line, lowercased and stripped."""
    lines = [ln.strip() for ln in stdout.splitlines() if ln.strip()]
    return lines[-1].lower() if lines else None


def verify(code: str) -> VerificationReport:
    """Run static then runtime checks; return the first failure or the runtime success."""
    static = static_check(code)
    if not static.passed:
        return static
    return runtime_check(code)
