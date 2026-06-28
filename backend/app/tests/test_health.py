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
