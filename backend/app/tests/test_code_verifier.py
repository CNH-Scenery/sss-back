from app.services.anthropic_client import FIXTURE_CODE
from app.services.code_verifier import runtime_check, static_check, verify

GOOD = '''\
def decide(features: dict, position: dict | None = None) -> dict:
    ma5 = features.get("ma5")
    ma20 = features.get("ma20")
    if ma5 is None or ma20 is None:
        return {"action": "HOLD", "size_ratio": 0.0, "reason": "no data", "indicators": {}}
    if ma5 > ma20:
        return {"action": "BUY", "size_ratio": 0.5, "reason": "up", "indicators": {}}
    return {"action": "HOLD", "size_ratio": 0.0, "reason": "flat", "indicators": {}}
'''

FORBIDDEN_IMPORT = '''\
import os

def decide(features, position=None):
    return {"action": "HOLD", "size_ratio": 0.0, "reason": "", "indicators": {}}
'''

MISSING_ENTRYPOINT = '''\
def other(features, position=None):
    return {"action": "HOLD"}
'''

NOT_NULL_SAFE = '''\
def decide(features: dict, position: dict | None = None) -> dict:
    # crashes when ma5 is None -> violates null-safety
    if features["ma5"] > features["ma20"]:
        return {"action": "BUY", "size_ratio": 1.0, "reason": "x", "indicators": {}}
    return {"action": "HOLD", "size_ratio": 0.0, "reason": "y", "indicators": {}}
'''

BAD_ACTION = '''\
def decide(features: dict, position: dict | None = None) -> dict:
    return {"action": "MOON", "size_ratio": 0.5, "reason": "x", "indicators": {}}
'''


def test_static_check_accepts_fixture():
    assert static_check(FIXTURE_CODE).passed


def test_static_check_rejects_forbidden_import():
    report = static_check(FORBIDDEN_IMPORT)
    assert not report.passed
    assert any("os" in e for e in report.errors)


def test_static_check_requires_decide():
    report = static_check(MISSING_ENTRYPOINT)
    assert not report.passed
    assert any("decide" in e for e in report.errors)


def test_static_check_rejects_syntax_error():
    report = static_check("def decide(:\n  pass")
    assert not report.passed
    assert report.stage == "static"


def test_runtime_check_passes_on_valid_decide():
    report = runtime_check(GOOD)
    assert report.passed
    assert report.decision_sample["action"] in {"BUY", "SELL", "HOLD"}


def test_runtime_check_enforces_null_safety():
    # Returns BUY/HOLD on full features but raises on null features -> must fail.
    report = runtime_check(NOT_NULL_SAFE)
    assert not report.passed
    assert report.stage == "runtime"
    assert any("null-features" in e for e in report.errors)


def test_runtime_check_rejects_invalid_action():
    report = runtime_check(BAD_ACTION)
    assert not report.passed
    assert report.stage == "runtime"


def test_verify_short_circuits_on_static_failure():
    report = verify(FORBIDDEN_IMPORT)
    assert not report.passed
    assert report.stage == "static"


def test_verify_accepts_fixture():
    report = verify(FIXTURE_CODE)
    assert report.passed
    assert report.decision_sample["action"] in {"BUY", "SELL", "HOLD"}
