from app.services.anthropic_client import FIXTURE_CODE
from app.services.code_verifier import runtime_check, static_check, verify

GOOD_NO_NETWORK = '''\
def generate_signal(market: str, timeframe: str = "15m") -> dict:
    return {"action": "hold", "size_ratio": 0.0, "reason": "stub", "indicators": {}}
'''

FORBIDDEN_IMPORT = '''\
import os

def generate_signal(market: str, timeframe: str = "15m") -> dict:
    return {"action": "hold", "size_ratio": 0.0, "reason": "x", "indicators": {}}
'''

MISSING_ENTRYPOINT = '''\
def other(market, timeframe):
    return {}
'''

BAD_ACTION = '''\
def generate_signal(market: str, timeframe: str = "15m") -> dict:
    return {"action": "moon", "size_ratio": 0.5, "reason": "x", "indicators": {}}
'''

RAISES = '''\
def generate_signal(market: str, timeframe: str = "15m") -> dict:
    raise ValueError("boom")
'''


def test_static_check_accepts_fixture():
    assert static_check(FIXTURE_CODE).passed


def test_static_check_rejects_forbidden_import():
    report = static_check(FORBIDDEN_IMPORT)
    assert not report.passed
    assert any("os" in e for e in report.errors)


def test_static_check_requires_entrypoint():
    report = static_check(MISSING_ENTRYPOINT)
    assert not report.passed
    assert any("generate_signal" in e for e in report.errors)


def test_static_check_rejects_syntax_error():
    report = static_check("def generate_signal(:\n    pass")
    assert not report.passed
    assert report.stage == "static"


def test_runtime_check_passes_on_valid_decision():
    report = runtime_check(GOOD_NO_NETWORK)
    assert report.passed
    assert report.decision_sample["action"] == "hold"


def test_runtime_check_rejects_invalid_action():
    report = runtime_check(BAD_ACTION)
    assert not report.passed
    assert report.stage == "runtime"


def test_runtime_check_rejects_exception():
    report = runtime_check(RAISES)
    assert not report.passed
    assert report.stage == "runtime"


def test_verify_short_circuits_on_static_failure():
    # Forbidden import must fail before we ever execute the code.
    report = verify(FORBIDDEN_IMPORT)
    assert not report.passed
    assert report.stage == "static"


def test_verify_accepts_fixture_module():
    # FIXTURE_CODE degrades to a valid "hold" decision even with no network access.
    report = verify(FIXTURE_CODE)
    assert report.passed
    assert report.decision_sample["action"] in {"buy", "sell", "hold"}
