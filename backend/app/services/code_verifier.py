"""Verifies LLM-generated `decide` functions: static analysis + contract probes.

  static_check  — AST: enforce the import allowlist, reject forbidden symbols, and
                  confirm a top-level `decide` function is defined.
  runtime_check — run decide() in the isolated engine against (a) a full feature dict
                  and (b) an all-None feature dict; BOTH must return a valid
                  BUY/SELL/HOLD Decision without raising (null-safety is enforced here).
"""
import ast
from dataclasses import dataclass, field
from typing import Any

from pydantic import ValidationError

from app.schemas import Decision
from app.services import strategy_engine
from app.services.code_contract import (
    ALLOWED_IMPORTS,
    ENTRYPOINT_NAME,
    FORBIDDEN_NAMES,
    NULL_FEATURES,
    SAMPLE_FEATURES,
    SAMPLE_POSITION,
)


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
                if alias.name.split(".")[0] not in ALLOWED_IMPORTS:
                    errors.append(f"import '{alias.name}' is not in the allowlist")
        elif isinstance(node, ast.ImportFrom):
            if (node.module or "").split(".")[0] not in ALLOWED_IMPORTS:
                errors.append(f"import from '{node.module}' is not in the allowlist")
        elif isinstance(node, ast.Name) and node.id in FORBIDDEN_NAMES:
            errors.append(f"forbidden name '{node.id}' is used")
        elif isinstance(node, ast.Attribute) and node.attr in FORBIDDEN_NAMES:
            errors.append(f"forbidden attribute '.{node.attr}' is used")

    if not any(isinstance(n, ast.FunctionDef) and n.name == ENTRYPOINT_NAME for n in tree.body):
        errors.append(f"module must define a top-level '{ENTRYPOINT_NAME}' function")

    errors = list(dict.fromkeys(errors))
    return VerificationReport(passed=not errors, stage="static", errors=errors)


def runtime_check(code: str) -> VerificationReport:
    result = strategy_engine.evaluate(
        code,
        [
            {"features": SAMPLE_FEATURES, "position": SAMPLE_POSITION},
            {"features": NULL_FEATURES, "position": None},
        ],
    )
    if "engine_error" in result:
        return VerificationReport(False, "runtime", [result["engine_error"]])

    results = result.get("results", [])
    if len(results) != 2:
        return VerificationReport(False, "runtime", ["engine did not return both probe results"])

    errors: list[str] = []
    decision_sample: dict[str, Any] | None = None
    for label, probe in zip(("full-features", "null-features"), results):
        if not probe.get("ok"):
            errors.append(f"{label}: decide raised — {probe.get('error')}")
            continue
        try:
            decision = Decision.model_validate(probe["decision"])
        except ValidationError as exc:
            errors.append(f"{label}: decision does not match contract — {exc}")
            continue
        if label == "full-features":
            decision_sample = decision.model_dump()

    if errors:
        return VerificationReport(False, "runtime", errors)
    return VerificationReport(passed=True, stage="ok", decision_sample=decision_sample)


def verify(code: str) -> VerificationReport:
    static = static_check(code)
    if not static.passed:
        return static
    return runtime_check(code)
