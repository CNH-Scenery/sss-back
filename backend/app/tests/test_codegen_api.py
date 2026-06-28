from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, create_engine

from app.db import create_db_and_tables, get_session
from app.main import app


@pytest.fixture()
def client(monkeypatch) -> Generator[TestClient, None, None]:
    # Fixture mode: the harness returns a known-good module without calling Anthropic.
    monkeypatch.setenv("CODEGEN_FIXTURE", "true")
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    create_db_and_tables(engine)

    def override_get_session() -> Generator[Session, None, None]:
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_session] = override_get_session
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


def test_generate_trading_code_passes_in_fixture_mode(client: TestClient):
    response = client.post(
        "/api/trading-code/generate",
        json={"prompt": "Buy when short MA crosses above long MA"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["passed"] is True
    assert body["status"] == "passed"
    assert body["model_name"] == "fixture"
    assert body["code_id"]
    assert "__main__" in body["code"]
    assert body["decision_sample"]["action"] in {"buy", "reject"}


def test_latest_returns_the_generated_record(client: TestClient):
    client.post(
        "/api/trading-code/generate",
        json={"prompt": "Mean reversion on RSI"},
    )

    latest = client.get("/api/trading-code/latest")
    assert latest.status_code == 200
    assert latest.json()["passed"] is True


def test_latest_404_when_empty(client: TestClient):
    assert client.get("/api/trading-code/latest").status_code == 404
