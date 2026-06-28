from collections.abc import Generator
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.engine import Engine
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, create_engine, select

from app.api.strategies import get_llm_service as get_strategy_llm_service
from app.db import create_db_and_tables, get_session
from app.main import app
from app.models import TwinStrategy


@pytest.fixture()
def client_and_engine() -> Generator[tuple[TestClient, Engine], None, None]:
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
        yield TestClient(app), engine
    finally:
        app.dependency_overrides.clear()


def submit_responses(client: TestClient) -> None:
    scenarios = client.get("/api/scenarios").json()["items"]
    for index, scenario in enumerate(scenarios):
        response = client.post(
            "/api/responses",
            json={
                "scenario_id": scenario["id"],
                "decision": "buy" if index % 2 == 0 else "wait",
                "natural_reason": f"{scenario['market']} 조건을 확인한다.",
                "confidence": 0.65,
                "preferred_action": "wait_for_confirmation",
            },
        )
        assert response.status_code == 200


def create_twin_context(client: TestClient) -> str:
    submit_responses(client)
    response = client.post("/api/twin-contexts/generate")
    assert response.status_code == 200
    return response.json()["context_id"]


def valid_strategy_payload(**overrides: Any) -> dict[str, Any]:
    payload = {
        "strategy_name": "Volume Breakout Confirmation",
        "summary": "거래량 증가와 돌파 지속을 확인한 뒤 제한적으로 진입합니다.",
        "timeframe": "15m",
        "entry_threshold": 0.65,
        "position_size": 0.25,
        "rules": [
            {
                "feature": "volume_ratio_n",
                "operator": "gte",
                "threshold": 1.2,
                "weight": 0.35,
            }
        ],
        "risk": {
            "stop_loss_pct": 0.03,
            "take_profit_pct": 0.06,
            "max_daily_entries": 3,
        },
    }
    payload.update(overrides)
    return payload


def test_generate_strategy_requires_existing_context(client_and_engine: tuple[TestClient, Engine]):
    client, _ = client_and_engine

    response = client.post(
        "/api/strategies/generate",
        json={"context_id": "00000000-0000-4000-8000-000000000000"},
    )

    assert response.status_code == 404


def test_generate_strategy_validates_and_stores_latest(client_and_engine: tuple[TestClient, Engine]):
    client, engine = client_and_engine
    context_id = create_twin_context(client)

    generated = client.post("/api/strategies/generate", json={"context_id": context_id})
    latest = client.get("/api/strategies/latest")

    assert generated.status_code == 200
    body = generated.json()
    assert body["strategy_id"]
    assert body["version"] == 1
    assert body["strategy_name"]
    assert body["entry_threshold"] == 0.65
    assert latest.status_code == 200
    assert latest.json() == body

    with Session(engine) as session:
        strategy = session.exec(select(TwinStrategy)).one()
        assert strategy.status == "validated"
        assert strategy.strategy_json["entry_threshold"] == 0.65


def test_generate_strategy_increments_versions(client_and_engine: tuple[TestClient, Engine]):
    client, _ = client_and_engine
    context_id = create_twin_context(client)

    first = client.post("/api/strategies/generate", json={"context_id": context_id})
    second = client.post("/api/strategies/generate", json={"context_id": context_id})
    latest = client.get("/api/strategies/latest")

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["version"] == 1
    assert second.json()["version"] == 2
    assert latest.json()["version"] == 2


@pytest.mark.parametrize(
    "payload",
    [
        valid_strategy_payload(
            rules=[
                {
                    "feature": "unknown_feature",
                    "operator": "gte",
                    "threshold": 1.2,
                    "weight": 0.35,
                }
            ]
        ),
        valid_strategy_payload(
            rules=[
                {
                    "feature": "volume_ratio_n",
                    "operator": "crosses",
                    "threshold": 1.2,
                    "weight": 0.35,
                }
            ]
        ),
        valid_strategy_payload(
            rules=[
                {
                    "feature": "volume_ratio_n",
                    "operator": "gte",
                    "threshold": 1.2,
                    "weight": 1.2,
                }
            ]
        ),
        valid_strategy_payload(position_size=1.2),
        valid_strategy_payload(entry_threshold=-0.1),
    ],
)
def test_generate_strategy_rejects_invalid_payloads(
    client_and_engine: tuple[TestClient, Engine],
    payload: dict[str, Any],
):
    class BrokenLLMService:
        def generate_strategy(self, twin_context):
            return payload

    client, engine = client_and_engine
    context_id = create_twin_context(client)
    app.dependency_overrides[get_strategy_llm_service] = lambda: BrokenLLMService()
    try:
        generated = client.post("/api/strategies/generate", json={"context_id": context_id})
        latest = client.get("/api/strategies/latest")
    finally:
        del app.dependency_overrides[get_strategy_llm_service]

    assert generated.status_code == 422
    assert latest.status_code == 404
    with Session(engine) as session:
        assert session.exec(select(TwinStrategy)).all() == []
