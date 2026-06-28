from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, create_engine

from app.api.twin_contexts import get_llm_service
from app.db import create_db_and_tables, get_session
from app.main import app


@pytest.fixture()
def client() -> Generator[TestClient, None, None]:
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


def submit_responses(client: TestClient, count: int) -> None:
    scenarios = client.get("/api/scenarios").json()["items"]
    decisions = ["buy", "wait", "take_profit", "stop_loss", "uncertain"]
    for index, scenario in enumerate(scenarios[:count]):
        response = client.post(
            "/api/responses",
            json={
                "scenario_id": scenario["id"],
                "decision": decisions[index % len(decisions)],
                "natural_reason": f"{scenario['market']} {index}번 상황은 거래량과 꼬리 위치를 함께 본다.",
                "confidence": 0.55 + (index % 4) * 0.1,
                "preferred_action": "wait_for_confirmation",
            },
        )
        assert response.status_code == 200


def test_generate_twin_context_requires_ten_responses(client: TestClient):
    submit_responses(client, 9)

    response = client.post("/api/twin-contexts/generate")

    assert response.status_code == 400
    assert "10" in response.json()["detail"]


def test_generate_twin_context_validates_and_stores_latest(client: TestClient):
    submit_responses(client, 10)

    generated = client.post("/api/twin-contexts/generate")
    latest = client.get("/api/twin-contexts/latest")

    assert generated.status_code == 200
    body = generated.json()
    assert body["context_id"]
    assert body["version"] == 1
    assert body["style_summary"]
    assert body["important_signals"]
    assert body["avoid_conditions"]
    assert body["uncertainty"]
    assert latest.status_code == 200
    assert latest.json() == body


def test_generate_twin_context_increments_versions(client: TestClient):
    submit_responses(client, 10)

    first = client.post("/api/twin-contexts/generate")
    second = client.post("/api/twin-contexts/generate")
    latest = client.get("/api/twin-contexts/latest")

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["version"] == 1
    assert second.json()["version"] == 2
    assert latest.json()["version"] == 2


def test_generate_twin_context_rejects_invalid_llm_payload(client: TestClient):
    class BrokenLLMService:
        def analyze_user_responses(self, responses):
            return {
                "style_summary": "",
                "important_signals": [],
                "avoid_conditions": [],
                "uncertainty": [],
                "decision_profile": {},
                "confidence_profile": {},
            }

    submit_responses(client, 10)
    app.dependency_overrides[get_llm_service] = lambda: BrokenLLMService()
    try:
        generated = client.post("/api/twin-contexts/generate")
        latest = client.get("/api/twin-contexts/latest")
    finally:
        del app.dependency_overrides[get_llm_service]

    assert generated.status_code == 502
    assert latest.status_code == 404
