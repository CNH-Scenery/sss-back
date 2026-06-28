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


def _generate(client: TestClient) -> str:
    resp = client.post(
        "/api/trading-code/generate",
        json={"prompt": "Buy when short MA is above long MA"},
    )
    assert resp.status_code == 200
    return resp.json()["code_id"]


def test_run_executes_and_persists(client: TestClient):
    code_id = _generate(client)
    resp = client.post(f"/api/trading-code/{code_id}/run")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["decision"] in {"buy", "reject"}
    assert body["run_id"]
    assert body["code_id"] == code_id


def test_runs_history_lists_recent(client: TestClient):
    code_id = _generate(client)
    client.post(f"/api/trading-code/{code_id}/run")
    client.post(f"/api/trading-code/{code_id}/run")
    runs = client.get(f"/api/trading-code/{code_id}/runs")
    assert runs.status_code == 200
    assert len(runs.json()) >= 2


def test_run_404_for_unknown_code(client: TestClient):
    import uuid

    resp = client.post(f"/api/trading-code/{uuid.uuid4()}/run")
    assert resp.status_code == 404


def test_stream_pushes_a_decision(client: TestClient):
    code_id = _generate(client)
    with client.websocket_connect(f"/api/trading-code/{code_id}/stream?interval=2") as ws:
        msg = ws.receive_json()
    assert msg["type"] == "decision"
    assert msg["status"] == "ok"
    assert msg["decision"] in {"buy", "reject"}
    assert msg["run_id"]
