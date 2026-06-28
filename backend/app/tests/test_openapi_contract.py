from fastapi.testclient import TestClient

from app.main import app


EXPECTED_PATHS = {
    "/health",
    "/api/auth/signup",
    "/api/auth/login",
    "/api/auth/me",
    "/api/scenarios",
    "/api/responses",
    "/api/responses/me",
    "/api/twin-contexts/generate",
    "/api/twin-contexts/latest",
    "/api/strategies/generate",
    "/api/strategies/latest",
    "/api/strategies/{strategy_id}/regenerate",
    "/api/strategies/{strategy_id}/activate",
    "/api/backtests/run",
    "/api/backtests/{backtest_run_id}",
    "/api/feedbacks",
    "/api/watchlists",
    "/api/signals",
    "/api/signals/{signal_id}/approve",
    "/api/signals/{signal_id}/reject",
    "/api/signals/{signal_id}/mark-not-me",
}


def test_openapi_exposes_session_1_api_contract():
    client = TestClient(app)

    response = client.get("/openapi.json")

    assert response.status_code == 200
    paths = set(response.json()["paths"].keys())
    assert EXPECTED_PATHS.issubset(paths)
