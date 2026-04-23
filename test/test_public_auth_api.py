from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path

from fastapi.testclient import TestClient

from services.api import create_app
from services.config import config


@contextmanager
def with_public_billing_file(path: Path):
    original = config.public_billing_file
    object.__setattr__(config, "public_billing_file", path)
    try:
        yield
    finally:
        object.__setattr__(config, "public_billing_file", original)


def test_register_creates_user_sets_cookie_and_returns_balance(tmp_path: Path) -> None:
    with with_public_billing_file(tmp_path / "public_billing.db"):
        client = TestClient(create_app())
        response = client.post("/api/public-auth/register", json={"username": "demo", "password": "secret"})

    assert response.status_code == 200
    assert response.json()["user"]["balance"] == "1.00"
    assert "set-cookie" in response.headers


def test_login_rejects_invalid_password(tmp_path: Path) -> None:
    with with_public_billing_file(tmp_path / "public_billing.db"):
        client = TestClient(create_app())
        client.post("/api/public-auth/register", json={"username": "demo", "password": "secret"})
        response = client.post("/api/public-auth/login", json={"username": "demo", "password": "wrong"})

    assert response.status_code == 401


def test_redeem_requires_login(tmp_path: Path) -> None:
    with with_public_billing_file(tmp_path / "public_billing.db"):
        client = TestClient(create_app())
        response = client.post("/api/public-auth/redeem")

    assert response.status_code == 401


def test_me_returns_current_user_and_logout_clears_session_cookie(tmp_path: Path) -> None:
    with with_public_billing_file(tmp_path / "public_billing.db"):
        client = TestClient(create_app())
        register_response = client.post(
            "/api/public-auth/register",
            json={"username": "demo", "password": "secret"},
        )
        me_response = client.get("/api/public-auth/me")
        logout_response = client.post("/api/public-auth/logout")
        me_after_logout_response = client.get("/api/public-auth/me")

    assert register_response.status_code == 200
    assert me_response.status_code == 200
    assert me_response.json()["user"]["username"] == "demo"
    assert logout_response.status_code == 200
    assert "set-cookie" in logout_response.headers
    assert me_after_logout_response.status_code == 401
