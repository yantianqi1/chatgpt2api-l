from __future__ import annotations

from contextlib import contextmanager
import json
from pathlib import Path
from unittest.mock import ANY, patch

from fastapi.testclient import TestClient

from services.api import create_app
from services.api_public_auth import SESSION_COOKIE_NAME
from services.chatgpt_service import ChatGPTService
from services.config import config
from services.image_service import ImageGenerationError
from services.public_auth_service import PublicAuthService
from services.public_billing_store import PublicBillingStore


def write_public_panel_file(
    path: Path,
    *,
    enabled: bool,
    mode: str = "fixed",
    quota_unit: str = "points",
    daily_limit: int = 0,
    daily_used: int = 0,
    daily_reset_date: str = "2026-04-22",
    fixed_quota: int = 0,
) -> None:
    path.write_text(
        json.dumps(
            {
                "enabled": enabled,
                "title": "studio",
                "description": "demo",
                "mode": mode,
                "quota_unit": quota_unit,
                "daily_limit": daily_limit,
                "daily_used": daily_used,
                "daily_reset_date": daily_reset_date,
                "fixed_quota": fixed_quota,
                "updated_at": "2026-04-22T00:00:00Z",
            }
        ),
        encoding="utf-8",
    )


@contextmanager
def with_public_panel_file(path: Path):
    original = config.public_panel_file
    object.__setattr__(config, "public_panel_file", path)
    try:
        yield
    finally:
        object.__setattr__(config, "public_panel_file", original)


@contextmanager
def with_public_billing_file(path: Path):
    original = config.public_billing_file
    object.__setattr__(config, "public_billing_file", path)
    try:
        yield
    finally:
        object.__setattr__(config, "public_billing_file", original)


def _admin_headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {config.auth_key}"}


def _issue_public_session(db_file: Path, *, username: str, balance_cents: int) -> tuple[str, str]:
    store = PublicBillingStore(db_file)
    user = store.create_user(username=username, password_hash="hash", signup_bonus_cents=balance_cents)
    auth_service = PublicAuthService(store)
    token, _ = auth_service.create_session(user["id"])
    return token, user["id"]


def test_public_status_does_not_require_admin_auth(tmp_path: Path) -> None:
    store_file = tmp_path / "public_panel.json"
    write_public_panel_file(store_file, enabled=True, mode="fixed", fixed_quota=5)

    with with_public_panel_file(store_file):
        client = TestClient(create_app())
        response = client.get("/api/public-panel/status")

    assert response.status_code == 200
    payload = response.json()
    assert payload["mode"] == "fixed"
    assert payload["available_quota"] == 5
    assert payload["quota"] == 5


def test_legacy_public_panel_quota_in_cents_is_migrated_to_points(tmp_path: Path) -> None:
    store_file = tmp_path / "public_panel.json"
    store_file.write_text(
        json.dumps(
            {
                "enabled": True,
                "title": "studio",
                "description": "demo",
                "mode": "fixed",
                "quota_unit": "cents",
                "fixed_quota": 500,
                "updated_at": "2026-04-22T00:00:00Z",
            }
        ),
        encoding="utf-8",
    )

    with with_public_panel_file(store_file):
        client = TestClient(create_app())
        response = client.get("/api/public-panel/status")

    assert response.status_code == 200
    payload = response.json()
    assert payload["quota_unit"] == "points"
    assert payload["fixed_quota"] == 5


def test_admin_public_panel_config_requires_auth(tmp_path: Path) -> None:
    store_file = tmp_path / "public_panel.json"
    write_public_panel_file(store_file, enabled=True, mode="fixed", fixed_quota=5)

    with with_public_panel_file(store_file):
        client = TestClient(create_app())
        response = client.get("/api/public-panel/config")

    assert response.status_code == 401


def test_admin_can_update_public_panel_config_with_auth(tmp_path: Path) -> None:
    store_file = tmp_path / "public_panel.json"
    write_public_panel_file(store_file, enabled=False, mode="fixed", fixed_quota=5)

    with with_public_panel_file(store_file):
        client = TestClient(create_app())
        response = client.post(
            "/api/public-panel/config",
            headers=_admin_headers(),
            json={
                "enabled": True,
                "title": "公开生图",
                "description": "匿名可用",
                "mode": "daily",
                "daily_limit": 20,
                "fixed_quota": 7,
            },
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["mode"] == "daily"
    assert payload["daily_limit"] == 20
    saved = json.loads(store_file.read_text(encoding="utf-8"))
    assert saved["mode"] == "daily"
    assert saved["daily_limit"] == 20


def test_fixed_mode_quota_add_requires_auth_and_updates_quota(tmp_path: Path) -> None:
    store_file = tmp_path / "public_panel.json"
    write_public_panel_file(store_file, enabled=True, mode="fixed", fixed_quota=5)

    with with_public_panel_file(store_file):
        client = TestClient(create_app())
        response = client.post(
            "/api/public-panel/quota/add",
            headers=_admin_headers(),
            json={"amount": 3},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["fixed_quota"] == 8
    saved = json.loads(store_file.read_text(encoding="utf-8"))
    assert saved["fixed_quota"] == 8


def test_public_generation_commits_quota_on_success(tmp_path: Path) -> None:
    panel_file = tmp_path / "public_panel.json"
    billing_file = tmp_path / "public_billing.db"
    write_public_panel_file(panel_file, enabled=True, mode="fixed", fixed_quota=500)

    with with_public_panel_file(panel_file), with_public_billing_file(billing_file):
        with patch.object(
            ChatGPTService,
            "generate_with_pool",
            autospec=True,
            return_value={"created": 1, "data": [{"b64_json": "abc"}]},
        ) as mocked_generate:
            client = TestClient(create_app(), base_url="https://testserver")
            response = client.post(
                "/api/public-panel/images/generations",
                json={"prompt": "cat", "model": "gpt-image-1", "n": 2},
            )

    assert response.status_code == 200
    mocked_generate.assert_called_once_with(ANY, "cat", "gpt-image-1", 2, "url")
    saved = json.loads(panel_file.read_text(encoding="utf-8"))
    assert saved["fixed_quota"] == 498


def test_public_generation_defaults_to_gpt_image_2_when_model_is_omitted(tmp_path: Path) -> None:
    panel_file = tmp_path / "public_panel.json"
    billing_file = tmp_path / "public_billing.db"
    write_public_panel_file(panel_file, enabled=True, mode="fixed", fixed_quota=500)

    with with_public_panel_file(panel_file), with_public_billing_file(billing_file):
        with patch.object(
            ChatGPTService,
            "generate_with_pool",
            autospec=True,
            return_value={"created": 1, "data": [{"b64_json": "abc"}]},
        ) as mocked_generate:
            client = TestClient(create_app(), base_url="https://testserver")
            response = client.post(
                "/api/public-panel/images/generations",
                json={"prompt": "cat", "n": 1},
            )

    assert response.status_code == 200
    mocked_generate.assert_called_once_with(ANY, "cat", "gpt-image-2", 1, "url")


def test_public_generation_rolls_back_quota_on_failure(tmp_path: Path) -> None:
    panel_file = tmp_path / "public_panel.json"
    billing_file = tmp_path / "public_billing.db"
    write_public_panel_file(panel_file, enabled=True, mode="fixed", fixed_quota=500)

    with with_public_panel_file(panel_file), with_public_billing_file(billing_file):
        with patch.object(ChatGPTService, "generate_with_pool", side_effect=ImageGenerationError("boom")):
            client = TestClient(create_app(), base_url="https://testserver")
            response = client.post(
                "/api/public-panel/images/generations",
                json={"prompt": "cat", "model": "gpt-image-1", "n": 2},
            )

    assert response.status_code == 502
    saved = json.loads(panel_file.read_text(encoding="utf-8"))
    assert saved["fixed_quota"] == 500


def test_authenticated_public_generation_uses_user_balance_not_public_panel(tmp_path: Path) -> None:
    panel_file = tmp_path / "public_panel.json"
    billing_file = tmp_path / "public_billing.db"
    write_public_panel_file(panel_file, enabled=True, mode="fixed", fixed_quota=500)
    token, user_id = _issue_public_session(billing_file, username="demo", balance_cents=500)

    with with_public_panel_file(panel_file), with_public_billing_file(billing_file):
        with patch.object(
            ChatGPTService,
            "generate_with_pool",
            autospec=True,
            return_value={"created": 1, "data": [{"b64_json": "abc"}]},
        ) as mocked_generate:
            client = TestClient(create_app(), base_url="https://testserver")
            client.cookies.set(SESSION_COOKIE_NAME, token)
            response = client.post(
                "/api/public-panel/images/generations",
                json={"prompt": "cat", "model": "gpt-image-1", "n": 2},
            )

    assert response.status_code == 200
    mocked_generate.assert_called_once_with(ANY, "cat", "gpt-image-1", 2, "url")
    saved = json.loads(panel_file.read_text(encoding="utf-8"))
    assert saved["fixed_quota"] == 500
    store = PublicBillingStore(billing_file)
    assert store.get_user_balance_cents(user_id) == 300


def test_authenticated_public_generation_fails_when_balance_is_insufficient(tmp_path: Path) -> None:
    panel_file = tmp_path / "public_panel.json"
    billing_file = tmp_path / "public_billing.db"
    write_public_panel_file(panel_file, enabled=True, mode="fixed", fixed_quota=500)
    token, user_id = _issue_public_session(billing_file, username="demo", balance_cents=100)

    with with_public_panel_file(panel_file), with_public_billing_file(billing_file):
        with patch.object(
            ChatGPTService,
            "generate_with_pool",
            autospec=True,
            return_value={"created": 1, "data": [{"b64_json": "abc"}]},
        ) as mocked_generate:
            client = TestClient(create_app(), base_url="https://testserver")
            client.cookies.set(SESSION_COOKIE_NAME, token)
            response = client.post(
                "/api/public-panel/images/generations",
                json={"prompt": "cat", "model": "gpt-image-1", "n": 2},
            )

    assert response.status_code == 403
    assert response.json()["detail"]["error"] == "public user balance is insufficient"
    mocked_generate.assert_not_called()
    saved = json.loads(panel_file.read_text(encoding="utf-8"))
    assert saved["fixed_quota"] == 500
    store = PublicBillingStore(billing_file)
    assert store.get_user_balance_cents(user_id) == 100


def test_invalid_public_session_does_not_fallback_to_anonymous_quota(tmp_path: Path) -> None:
    panel_file = tmp_path / "public_panel.json"
    billing_file = tmp_path / "public_billing.db"
    write_public_panel_file(panel_file, enabled=True, mode="fixed", fixed_quota=500)

    with with_public_panel_file(panel_file), with_public_billing_file(billing_file):
        with patch.object(
            ChatGPTService,
            "generate_with_pool",
            autospec=True,
            return_value={"created": 1, "data": [{"b64_json": "abc"}]},
        ) as mocked_generate:
            client = TestClient(create_app(), base_url="https://testserver")
            client.cookies.set(SESSION_COOKIE_NAME, "invalid-session-token")
            response = client.post(
                "/api/public-panel/images/generations",
                json={"prompt": "cat", "model": "gpt-image-1", "n": 2},
            )

    assert response.status_code == 401
    assert response.json()["detail"]["error"] == "login required"
    mocked_generate.assert_not_called()
    saved = json.loads(panel_file.read_text(encoding="utf-8"))
    assert saved["fixed_quota"] == 500


def test_public_generation_returns_403_when_model_price_is_unavailable(tmp_path: Path) -> None:
    panel_file = tmp_path / "public_panel.json"
    billing_file = tmp_path / "public_billing.db"
    write_public_panel_file(panel_file, enabled=True, mode="fixed", fixed_quota=500)

    store = PublicBillingStore(billing_file)
    store.update_model_pricing(model="gpt-image-1", price_cents=100, enabled=False)

    with with_public_panel_file(panel_file), with_public_billing_file(billing_file):
        client = TestClient(create_app(), base_url="https://testserver")
        response = client.post(
            "/api/public-panel/images/generations",
            json={"prompt": "cat", "model": "gpt-image-1", "n": 1},
        )

    assert response.status_code == 403
    assert response.json()["detail"]["error"] == "model price is unavailable"


def test_anonymous_public_generation_still_uses_public_panel_quota(tmp_path: Path) -> None:
    panel_file = tmp_path / "public_panel.json"
    billing_file = tmp_path / "public_billing.db"
    write_public_panel_file(panel_file, enabled=True, mode="fixed", fixed_quota=500)

    with with_public_panel_file(panel_file), with_public_billing_file(billing_file):
        with patch.object(
            ChatGPTService,
            "generate_with_pool",
            autospec=True,
            return_value={"created": 1, "data": [{"b64_json": "abc"}]},
        ):
            client = TestClient(create_app(), base_url="https://testserver")
            response = client.post(
                "/api/public-panel/images/generations",
                json={"prompt": "cat", "model": "gpt-image-1", "n": 2},
            )

    assert response.status_code == 200
    saved = json.loads(panel_file.read_text(encoding="utf-8"))
    assert saved["fixed_quota"] == 498
