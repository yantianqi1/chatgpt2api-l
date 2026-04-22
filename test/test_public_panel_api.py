from __future__ import annotations

from contextlib import contextmanager
import json
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from services.api import create_app
from services.chatgpt_service import ChatGPTService
from services.config import config
from services.image_service import ImageGenerationError


def write_public_panel_file(
    path: Path,
    *,
    enabled: bool,
    mode: str = "fixed",
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


def _admin_headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {config.auth_key}"}


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
    store_file = tmp_path / "public_panel.json"
    write_public_panel_file(store_file, enabled=True, mode="fixed", fixed_quota=5)

    with with_public_panel_file(store_file):
        with patch.object(
            ChatGPTService,
            "generate_with_pool",
            return_value={"created": 1, "data": [{"b64_json": "abc"}]},
        ):
            client = TestClient(create_app())
            response = client.post(
                "/api/public-panel/images/generations",
                json={"prompt": "cat", "model": "gpt-image-1", "n": 2},
            )

    assert response.status_code == 200
    saved = json.loads(store_file.read_text(encoding="utf-8"))
    assert saved["fixed_quota"] == 3


def test_public_generation_rolls_back_quota_on_failure(tmp_path: Path) -> None:
    store_file = tmp_path / "public_panel.json"
    write_public_panel_file(store_file, enabled=True, mode="fixed", fixed_quota=5)

    with with_public_panel_file(store_file):
        with patch.object(ChatGPTService, "generate_with_pool", side_effect=ImageGenerationError("boom")):
            client = TestClient(create_app())
            response = client.post(
                "/api/public-panel/images/generations",
                json={"prompt": "cat", "model": "gpt-image-1", "n": 2},
            )

    assert response.status_code == 502
    saved = json.loads(store_file.read_text(encoding="utf-8"))
    assert saved["fixed_quota"] == 5
