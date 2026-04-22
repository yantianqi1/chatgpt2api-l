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


def write_public_panel_file(path: Path, *, enabled: bool, quota: int) -> None:
    path.write_text(
        json.dumps(
            {
                "enabled": enabled,
                "quota": quota,
                "title": "studio",
                "description": "demo",
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


def test_public_status_does_not_require_admin_auth(tmp_path: Path) -> None:
    store_file = tmp_path / "public_panel.json"
    write_public_panel_file(store_file, enabled=True, quota=5)

    with with_public_panel_file(store_file):
        client = TestClient(create_app())
        response = client.get("/api/public-panel/status")

    assert response.status_code == 200
    assert response.json()["quota"] == 5


def test_admin_public_panel_config_requires_auth(tmp_path: Path) -> None:
    store_file = tmp_path / "public_panel.json"
    write_public_panel_file(store_file, enabled=True, quota=5)

    with with_public_panel_file(store_file):
        client = TestClient(create_app())
        response = client.get("/api/public-panel/config")

    assert response.status_code == 401


def test_public_generation_commits_quota_on_success(tmp_path: Path) -> None:
    store_file = tmp_path / "public_panel.json"
    write_public_panel_file(store_file, enabled=True, quota=5)

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
    assert saved["quota"] == 3


def test_public_generation_rolls_back_quota_on_failure(tmp_path: Path) -> None:
    store_file = tmp_path / "public_panel.json"
    write_public_panel_file(store_file, enabled=True, quota=5)

    with with_public_panel_file(store_file):
        with patch.object(ChatGPTService, "generate_with_pool", side_effect=ImageGenerationError("boom")):
            client = TestClient(create_app())
            response = client.post(
                "/api/public-panel/images/generations",
                json={"prompt": "cat", "model": "gpt-image-1", "n": 2},
            )

    assert response.status_code == 502
    saved = json.loads(store_file.read_text(encoding="utf-8"))
    assert saved["quota"] == 5
