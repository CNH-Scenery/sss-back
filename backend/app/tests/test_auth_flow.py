from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, create_engine

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


def _signup(client: TestClient, **overrides):
    payload = {"name": "홍길동", "email": "trader@example.com", "password": "supersecret"}
    payload.update(overrides)
    return client.post("/api/auth/signup", json=payload)


def test_signup_creates_user_and_returns_token(client: TestClient):
    response = _signup(client)

    assert response.status_code == 201
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["access_token"]
    assert body["user"]["email"] == "trader@example.com"
    assert body["user"]["name"] == "홍길동"
    assert body["user"]["id"]


def test_signup_normalizes_email_and_rejects_duplicates(client: TestClient):
    first = _signup(client, email="Trader@Example.com")
    duplicate = _signup(client, email="trader@example.com", name="다른사람")

    assert first.status_code == 201
    assert first.json()["user"]["email"] == "trader@example.com"
    assert duplicate.status_code == 409


def test_signup_rejects_invalid_email_and_short_password(client: TestClient):
    bad_email = _signup(client, email="not-an-email")
    short_password = _signup(client, password="short")

    assert bad_email.status_code == 422
    assert short_password.status_code == 422


def test_login_succeeds_with_valid_credentials(client: TestClient):
    _signup(client)

    response = client.post(
        "/api/auth/login",
        json={"email": "TRADER@example.com", "password": "supersecret"},
    )

    assert response.status_code == 200
    assert response.json()["user"]["email"] == "trader@example.com"
    assert response.json()["access_token"]


def test_login_fails_with_wrong_password(client: TestClient):
    _signup(client)

    response = client.post(
        "/api/auth/login",
        json={"email": "trader@example.com", "password": "wrongpassword"},
    )

    assert response.status_code == 401


def test_login_fails_for_unknown_email(client: TestClient):
    response = client.post(
        "/api/auth/login",
        json={"email": "ghost@example.com", "password": "supersecret"},
    )

    assert response.status_code == 401


def test_me_returns_current_user_with_valid_token(client: TestClient):
    token = _signup(client).json()["access_token"]

    response = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    assert response.json()["email"] == "trader@example.com"


def test_me_requires_authentication(client: TestClient):
    missing = client.get("/api/auth/me")
    invalid = client.get("/api/auth/me", headers={"Authorization": "Bearer not.a.token"})

    assert missing.status_code == 401
    assert invalid.status_code == 401
