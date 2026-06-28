from collections.abc import Generator
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, create_engine

from app.db import create_db_and_tables, get_session
from app.main import app


def _synthetic_candles(n: int = 120) -> list[dict]:
    base = datetime(2024, 1, 1, tzinfo=timezone.utc)
    out = []
    price = 100.0
    for i in range(n):
        price *= 1.02 if i % 3 else 0.98
        out.append({
            "market": "KRW-BTC",
            "timeframe": "1d",
            "candle_time": (base + timedelta(days=i)).isoformat(),
            "open": price,
            "high": price * 1.01,
            "low": price * 0.99,
            "close": price,
            "volume": 1000 + i,
        })
    return out


@pytest.fixture()
def client(monkeypatch) -> Generator[TestClient, None, None]:
    monkeypatch.setenv("CODEGEN_FIXTURE", "true")
    # No network: feed synthetic candles to the backtester.
    monkeypatch.setattr(
        "app.services.backtester.fetch_candles",
        lambda **kwargs: _synthetic_candles(),
    )
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
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
    resp = client.post("/api/trading-code/generate", json={"prompt": "MA crossover"})
    assert resp.status_code == 200
    return resp.json()["code_id"]


def test_backtest_runs_and_returns_metrics(client: TestClient):
    code_id = _generate(client)
    resp = client.post(
        "/api/backtests/run",
        json={"code_id": code_id, "market": "KRW-BTC", "timeframe": "1d", "initial_cash": 1_000_000},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["backtest_run_id"]
    assert body["code_id"] == code_id
    metrics = body["metrics"]
    for key in ("totalReturn", "bhReturn", "winRate", "trades", "mdd", "vsBH"):
        assert key in metrics
    assert len(body["eq"]) == 120
    assert len(body["bh"]) == 120
    assert len(body["candles"]) == 120
    assert set(body["candles"][0]) >= {"t", "o", "h", "l", "c"}
    assert isinstance(body["markers"], list)


def test_backtest_result_is_retrievable(client: TestClient):
    code_id = _generate(client)
    run = client.post("/api/backtests/run", json={"code_id": code_id}).json()
    fetched = client.get(f"/api/backtests/{run['backtest_run_id']}")
    assert fetched.status_code == 200
    assert fetched.json()["backtest_run_id"] == run["backtest_run_id"]


def test_backtest_404_for_unknown_code(client: TestClient):
    import uuid

    resp = client.post("/api/backtests/run", json={"code_id": str(uuid.uuid4())})
    assert resp.status_code == 404
