from fastapi.testclient import TestClient

from app.main import app


def test_health_returns_ok_status():
    client = TestClient(app)

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_root_returns_api_landing_payload():
    client = TestClient(app)

    response = client.get("/")

    assert response.status_code == 200
    assert response.json() == {
        "name": "CoinTwin API",
        "status": "ok",
        "docs": "/docs",
        "health": "/health",
        "scenarios": "/api/scenarios",
    }


def test_vite_frontend_origin_is_allowed_for_auth_preflight():
    client = TestClient(app)

    response = client.options(
        "/api/auth/login",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"


def test_duplicate_slash_paths_are_normalized():
    client = TestClient(app)

    response = client.get("/api/auth//login")

    assert response.status_code == 405
    assert response.headers["allow"] == "POST"
