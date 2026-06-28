"""Verifies LLM-generated trading code: static analysis + sandboxed execution.

Two stages:
  static_check  — parse the AST, enforce the import allowlist, reject forbidden
                  symbols, and confirm the entrypoint is defined.
  runtime_check — run the module in an isolated subprocess (`python -I`) with a CPU
                  limit and wall-clock timeout, call generate_signal on sample input,
                  and validate the returned dict against the TradingDecision contract.

Network access (httpx) is intentionally allowed per the data-access decision, so this
is robustness verification, not a full security sandbox.
"""
import ast
import json
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from app.schemas import TradingDecision
from app.services.code_contract import (
    ALLOWED_IMPORTS,
    ENTRYPOINT_NAME,
    FORBIDDEN_NAMES,
    SAMPLE_MARKET,
    SAMPLE_TIMEFRAME,
)

RUNTIME_TIMEOUT_SECONDS = 20
CPU_LIMIT_SECONDS = 15
RESULT_MARKER = "__DECISION__"

_RUNNER = f"""
import sys, json, importlib.util
path, market, timeframe = sys.argv[1], sys.argv[2], sys.argv[3]
try:
    spec = importlib.util.spec_from_file_location("strategy_mod", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    fn = getattr(mod, "{ENTRYPOINT_NAME}")
    result = fn(market, timeframe)
    print("{RESULT_MARKER}" + json.dumps(result, default=str))
except Exception as exc:  # noqa: BLE001
    import traceback
    sys.stderr.write(traceback.format_exc())
    sys.exit(3)
"""


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

    has_entrypoint = any(
        isinstance(n, ast.FunctionDef) and n.name == ENTRYPOINT_NAME for n in tree.body
    )
    if not has_entrypoint:
        errors.append(f"module must define a top-level '{ENTRYPOINT_NAME}' function")

    # De-duplicate while preserving order.
    errors = list(dict.fromkeys(errors))
    return VerificationReport(passed=not errors and has_entrypoint, stage="static", errors=errors)


def _limit_resources() -> None:
    try:
        import resource

        resource.setrlimit(resource.RLIMIT_CPU, (CPU_LIMIT_SECONDS, CPU_LIMIT_SECONDS))
    except Exception:  # noqa: BLE001 - best effort; timeout is the hard backstop
        pass


def runtime_check(
    code: str,
    market: str = SAMPLE_MARKET,
    timeframe: str = SAMPLE_TIMEFRAME,
) -> VerificationReport:
    with tempfile.TemporaryDirectory() as tmp:
        strategy_path = Path(tmp) / "strategy_mod.py"
        strategy_path.write_text(code, encoding="utf-8")

        try:
            proc = subprocess.run(
                [sys.executable, "-I", "-c", _RUNNER, str(strategy_path), market, timeframe],
                capture_output=True,
                text=True,
                timeout=RUNTIME_TIMEOUT_SECONDS,
                preexec_fn=_limit_resources,
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

        line = next(
            (ln for ln in proc.stdout.splitlines() if ln.startswith(RESULT_MARKER)), None
        )
        if line is None:
            return VerificationReport(
                False, "runtime", ["no decision returned by generate_signal"], stdout=proc.stdout
            )

        raw = line[len(RESULT_MARKER):]
        try:
            payload = json.loads(raw)
            decision = TradingDecision.model_validate(payload)
        except (json.JSONDecodeError, ValidationError) as exc:
            return VerificationReport(
                False, "runtime", [f"decision did not match contract: {exc}"], stdout=proc.stdout
            )

        return VerificationReport(
            passed=True,
            stage="ok",
            decision_sample=decision.model_dump(),
            stdout=proc.stdout,
        )


def verify(code: str, market: str = SAMPLE_MARKET, timeframe: str = SAMPLE_TIMEFRAME) -> VerificationReport:
    """Run static then runtime checks; return the first failure or the runtime success."""
    static = static_check(code)
    if not static.passed:
        return static
    return runtime_check(code, market, timeframe)
