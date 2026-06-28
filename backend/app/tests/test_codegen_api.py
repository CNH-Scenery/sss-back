from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, create_engine

from app.db import create_db_and_tables, get_session
from app.main import app
from app.services.code_contract import SAMPLE_FEATURES


@pytest.fixture()
def client(monkeypatch) -> Generator[TestClient, None, None]:
    # Fixture mode: the harness returns a known-good decide() without calling Anthropic.
    monkeypatch.setenv("CODEGEN_FIXTURE", "true")
    # Live features without hitting the network.
    monkeypatch.setattr("app.api.codegen.compute_features", lambda market, timeframe: dict(SAMPLE_FEATURES))
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


def _generate(client: TestClient) -> str:
    resp = client.post(
        "/api/trading-code/generate",
        json={"prompt": "Buy when short MA crosses above long MA"},
    )
    assert resp.status_code == 200
    return resp.json()["code_id"]


def test_generate_emits_decide_function(client: TestClient):
    resp = client.post("/api/trading-code/generate", json={"prompt": "MA crossover"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["passed"] is True
    assert body["model_name"] == "fixture"
    assert "def decide" in body["code"]
    assert body["decision_sample"]["action"] in {"BUY", "SELL", "HOLD"}


def test_run_evaluates_live_features(client: TestClient):
    code_id = _generate(client)
    resp = client.post(f"/api/trading-code/{code_id}/run", params={"market": "KRW-BTC", "timeframe": "15m"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["decision"] in {"BUY", "SELL", "HOLD"}
    assert body["run_id"]


def test_runs_history(client: TestClient):
    code_id = _generate(client)
    client.post(f"/api/trading-code/{code_id}/run")
    client.post(f"/api/trading-code/{code_id}/run")
    runs = client.get(f"/api/trading-code/{code_id}/runs")
    assert runs.status_code == 200
    assert len(runs.json()) >= 2


def test_stream_pushes_alert(client: TestClient):
    code_id = _generate(client)
    with client.websocket_connect(f"/api/trading-code/{code_id}/stream?interval=2&market=KRW-BTC") as ws:
        msg = ws.receive_json()
    assert msg["type"] == "alert"
    assert msg["action"] in {"BUY", "SELL", "HOLD"}
    assert msg["market"] == "KRW-BTC"
    assert msg["price"] == SAMPLE_FEATURES["close"]


def test_run_404_for_unknown_code(client: TestClient):
    import uuid

    resp = client.post(f"/api/trading-code/{uuid.uuid4()}/run")
    assert resp.status_code == 404
