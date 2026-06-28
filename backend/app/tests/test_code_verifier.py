from app.services.anthropic_client import FIXTURE_CODE
from app.services.code_verifier import runtime_check, static_check, verify

GOOD_NO_NETWORK = '''\
print("reject")
'''

GOOD_BUY = '''\
if __name__ == "__main__":
    print("buy")
'''

FORBIDDEN_IMPORT = '''\
import os

print("reject")
'''

BAD_OUTPUT = '''\
print("moon")
'''

NO_OUTPUT = '''\
x = 1 + 1
'''

RAISES = '''\
raise ValueError("boom")
'''


def test_static_check_accepts_fixture():
    assert static_check(FIXTURE_CODE).passed


def test_static_check_rejects_forbidden_import():
    report = static_check(FORBIDDEN_IMPORT)
    assert not report.passed
    assert any("os" in e for e in report.errors)


def test_static_check_rejects_syntax_error():
    report = static_check("print(:\n")
    assert not report.passed
    assert report.stage == "static"


def test_runtime_check_passes_on_reject():
    report = runtime_check(GOOD_NO_NETWORK)
    assert report.passed
    assert report.decision_sample["action"] == "reject"


def test_runtime_check_passes_on_buy():
    report = runtime_check(GOOD_BUY)
    assert report.passed
    assert report.decision_sample["action"] == "buy"


def test_runtime_check_rejects_invalid_token():
    report = runtime_check(BAD_OUTPUT)
    assert not report.passed
    assert report.stage == "runtime"


def test_runtime_check_rejects_no_output():
    report = runtime_check(NO_OUTPUT)
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
    # FIXTURE_CODE degrades to a valid "reject" decision even with no network access.
    report = verify(FIXTURE_CODE)
    assert report.passed
    assert report.decision_sample["action"] in {"buy", "reject"}
