from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, create_engine, select

from app.db import create_db_and_tables, get_session
from app.main import app
from app.models import UserResponse


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


def test_scenarios_endpoint_returns_ten_seeded_scenarios(client: TestClient):
    response = client.get("/api/scenarios")

    assert response.status_code == 200
    body = response.json()
    assert len(body["items"]) == 10
    assert {item["timeframe"] for item in body["items"]} == {"15m"}
    assert all(item["description"] for item in body["items"])


def test_scenarios_endpoint_allows_frontend_origin(client: TestClient):
    response = client.get("/api/scenarios", headers={"Origin": "http://localhost:3000"})

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:3000"


def test_response_create_stores_response_and_updates_duplicate(client: TestClient):
    scenario_id = client.get("/api/scenarios").json()["items"][0]["id"]

    first = client.post(
        "/api/responses",
        json={
            "scenario_id": scenario_id,
            "decision": "wait",
            "natural_reason": "거래량은 좋지만 윗꼬리가 부담스럽다.",
            "confidence": 0.7,
            "preferred_action": "confirm_then_enter",
        },
    )
    second = client.post(
        "/api/responses",
        json={
            "scenario_id": scenario_id,
            "decision": "buy",
            "natural_reason": "재확인 후 돌파가 유지되어 소액 진입한다.",
            "confidence": 0.8,
            "preferred_action": "small_entry",
        },
    )
    mine = client.get("/api/responses/me")

    assert first.status_code == 200
    assert first.json()["response_count"] == 1
    assert first.json()["can_generate_twin"] is False
    assert second.status_code == 200
    assert second.json()["response_count"] == 1
    assert mine.status_code == 200
    assert mine.json()["response_count"] == 1
    assert mine.json()["items"][0]["decision"] == "buy"
    assert mine.json()["items"][0]["natural_reason"] == "재확인 후 돌파가 유지되어 소액 진입한다."


def test_twin_generation_flag_turns_true_after_ten_responses(client: TestClient):
    scenarios = client.get("/api/scenarios").json()["items"]

    for index, scenario in enumerate(scenarios):
        response = client.post(
            "/api/responses",
            json={
                "scenario_id": scenario["id"],
                "decision": "wait",
                "natural_reason": f"{index}번 상황은 더 확인하고 싶다.",
                "confidence": 0.6,
                "preferred_action": "wait_for_confirmation",
            },
        )
        assert response.status_code == 200

    mine = client.get("/api/responses/me")

    assert mine.json()["response_count"] == 10
    assert mine.json()["can_generate_twin"] is True


def test_response_rejects_invalid_confidence(client: TestClient):
    scenario_id = client.get("/api/scenarios").json()["items"][0]["id"]

    response = client.post(
        "/api/responses",
        json={
            "scenario_id": scenario_id,
            "decision": "wait",
            "natural_reason": "확신도 범위 검증",
            "confidence": 1.2,
            "preferred_action": "wait_for_confirmation",
        },
    )

    assert response.status_code == 422


def test_response_create_requires_existing_scenario(client: TestClient):
    response = client.post(
        "/api/responses",
        json={
            "scenario_id": "00000000-0000-0000-0000-000000000000",
            "decision": "wait",
            "natural_reason": "존재하지 않는 상황",
            "confidence": 0.5,
            "preferred_action": "wait_for_confirmation",
        },
    )

    assert response.status_code == 404
