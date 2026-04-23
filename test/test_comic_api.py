from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path

from fastapi.testclient import TestClient

from services.config import config


@contextmanager
def with_comic_projects_dir(path: Path):
    original = config.comic_projects_dir
    object.__setattr__(config, "comic_projects_dir", path)
    try:
        yield
    finally:
        object.__setattr__(config, "comic_projects_dir", original)


@contextmanager
def create_client(tmp_path: Path, monkeypatch):
    from services import api as api_module

    class FakeWatcherThread:
        def join(self, timeout: float | None = None) -> None:
            return None

    class FakeComicWorker:
        def __init__(self, *args, **kwargs) -> None:
            self.args = args
            self.kwargs = kwargs

        def start(self) -> None:
            return None

        def stop(self) -> None:
            return None

    monkeypatch.setattr(api_module, "start_limited_account_watcher", lambda stop_event: FakeWatcherThread())
    monkeypatch.setattr(api_module, "ComicWorker", FakeComicWorker)

    with with_comic_projects_dir(tmp_path / "comic-projects"):
        with TestClient(api_module.create_app()) as client:
            yield client


def test_project_crud_works_through_api(tmp_path: Path, monkeypatch) -> None:
    with create_client(tmp_path, monkeypatch) as client:
        create_response = client.post(
            "/api/comic/projects",
            json={
                "title": "银河列车",
                "source_text": "第一章：列车驶入暴风区。",
                "style_prompt": "赛博都市漫画",
            },
        )

        assert create_response.status_code == 201
        project = create_response.json()
        project_id = project["id"]

        list_response = client.get("/api/comic/projects")
        assert list_response.status_code == 200
        assert [item["id"] for item in list_response.json()] == [project_id]

        patch_response = client.patch(
            f"/api/comic/projects/{project_id}",
            json={
                "title": "银河列车·修订版",
                "source_text": "第一章：列车穿越雷暴云层。",
                "style_prompt": "冷色调电影漫画",
            },
        )
        assert patch_response.status_code == 200
        assert patch_response.json()["title"] == "银河列车·修订版"

        detail_response = client.get(f"/api/comic/projects/{project_id}")
        assert detail_response.status_code == 200
        snapshot = detail_response.json()
        assert snapshot["project"]["id"] == project_id
        assert snapshot["project"]["style_prompt"] == "冷色调电影漫画"
        assert snapshot["characters"] == []
        assert snapshot["chapters"] == []

        delete_response = client.delete(f"/api/comic/projects/{project_id}")
        assert delete_response.status_code == 204
        assert client.get("/api/comic/projects").json() == []


def test_import_endpoint_creates_task_without_blocking(tmp_path: Path, monkeypatch) -> None:
    with create_client(tmp_path, monkeypatch) as client:
        project_id = client.post(
            "/api/comic/projects",
            json={
                "title": "银河列车",
                "source_text": "",
                "style_prompt": "赛博都市漫画",
            },
        ).json()["id"]

        response = client.post(
            f"/api/comic/projects/{project_id}/import",
            json={"source_text": "第一章：列车驶入暴风区。", "import_mode": "full_text"},
        )

        assert response.status_code == 202
        payload = response.json()
        assert payload["task_id"]
        assert payload["status"] == "queued"


def test_chapter_script_generation_endpoint_returns_task_id(tmp_path: Path, monkeypatch) -> None:
    with create_client(tmp_path, monkeypatch) as client:
        project_id = client.post(
            "/api/comic/projects",
            json={
                "title": "银河列车",
                "source_text": "第一章：列车驶入暴风区。",
                "style_prompt": "赛博都市漫画",
            },
        ).json()["id"]
        client.patch(
            f"/api/comic/projects/{project_id}/chapters/chapter-1",
            json={
                "title": "第一章",
                "source_text": "列车驶入暴风区。",
                "summary": "列车进入危险空域。",
                "order": 1,
            },
        )

        response = client.post(f"/api/comic/projects/{project_id}/chapters/chapter-1/generate-script")

        assert response.status_code == 202
        assert response.json()["task_id"]


def test_scene_render_endpoint_returns_task_id(tmp_path: Path, monkeypatch) -> None:
    with create_client(tmp_path, monkeypatch) as client:
        project_id = client.post(
            "/api/comic/projects",
            json={
                "title": "银河列车",
                "source_text": "第一章：列车驶入暴风区。",
                "style_prompt": "赛博都市漫画",
            },
        ).json()["id"]
        client.patch(
            f"/api/comic/projects/{project_id}/scenes/scene-1",
            json={
                "chapter_id": "chapter-1",
                "title": "镜头一",
                "description": "列车穿过雷暴云层。",
                "prompt": "赛博列车穿过雷暴云层",
                "character_ids": [],
                "order": 1,
                "assets": [],
            },
        )

        response = client.post(f"/api/comic/projects/{project_id}/scenes/scene-1/render")

        assert response.status_code == 202
        assert response.json()["task_id"]


def test_task_list_endpoint_returns_progress_and_error_fields(tmp_path: Path, monkeypatch) -> None:
    with create_client(tmp_path, monkeypatch) as client:
        project_id = client.post(
            "/api/comic/projects",
            json={
                "title": "银河列车",
                "source_text": "第一章：列车驶入暴风区。",
                "style_prompt": "赛博都市漫画",
            },
        ).json()["id"]
        task_id = client.post(
            f"/api/comic/projects/{project_id}/import",
            json={"source_text": "第一章：列车驶入暴风区。", "import_mode": "full_text"},
        ).json()["task_id"]

        client.app.state.comic_task_service.update_task(
            task_id,
            status="failed",
            error="upstream exploded",
            progress=37,
        )

        response = client.get(f"/api/comic/tasks?project_id={project_id}")

        assert response.status_code == 200
        payload = response.json()
        assert len(payload) == 1
        assert payload[0]["progress"] == 37
        assert payload[0]["error"] == "upstream exploded"


def test_rendered_assets_are_served_from_comic_static_route(tmp_path: Path, monkeypatch) -> None:
    with create_client(tmp_path, monkeypatch) as client:
        project_id = client.post(
            "/api/comic/projects",
            json={
                "title": "银河列车",
                "source_text": "第一章：列车驶入暴风区。",
                "style_prompt": "赛博都市漫画",
            },
        ).json()["id"]
        asset_dir = tmp_path / "comic-projects" / project_id / "assets" / "scene-1"
        asset_dir.mkdir(parents=True, exist_ok=True)
        asset_path = asset_dir / "panel-1.png"
        asset_path.write_bytes(b"fake-png")

        response = client.get(f"/comic-assets/{project_id}/scene-1/panel-1.png")

        assert response.status_code == 200
        assert response.content == b"fake-png"
