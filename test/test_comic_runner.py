from __future__ import annotations

import base64
from pathlib import Path

from services.comic.models import ComicChapter, ComicScene
from services.comic.runner import ComicTaskRunner
from services.comic.store import ComicProjectStore
from services.comic.tasks import ComicTaskService


class FakeWorkflowService:
    def __init__(self) -> None:
        self.render_calls: list[str] = []

    def split_chapters(self, *, source_text: str, model: str) -> list[dict[str, object]]:
        return [
            {"title": "第一章", "summary": "暴风将至", "source_text": source_text, "order": 1},
            {"title": "第二章", "summary": "危机逼近", "source_text": f"{source_text}\n第二章", "order": 2},
        ]

    def generate_scene_script(
        self,
        *,
        chapter_text: str,
        style_prompt: str,
        characters,
        relevant_character_ids,
        model: str,
    ) -> list[dict[str, object]]:
        return [
            {
                "title": "镜头一",
                "description": chapter_text,
                "prompt": f"{style_prompt} - 镜头一",
                "character_ids": list(relevant_character_ids),
                "order": 1,
            }
        ]

    def render_scene(
        self,
        *,
        scene_description: str,
        style_prompt: str,
        characters,
        model: str,
        n: int,
    ) -> dict[str, object]:
        self.render_calls.append(scene_description)
        if "失败镜头" in scene_description:
            raise RuntimeError("upstream render failed")
        return {
            "created": 1,
            "data": [
                {
                    "b64_json": base64.b64encode(b"fake-image").decode(),
                    "revised_prompt": f"{style_prompt}::{scene_description}",
                }
            ],
        }


def _create_project(store: ComicProjectStore):
    return store.create_project(
        title="银河列车",
        source_text="第一章：列车驶入暴风区。",
        style_prompt="赛博都市漫画",
    )


def test_import_runner_creates_chapters_from_full_text(tmp_path: Path) -> None:
    store = ComicProjectStore(tmp_path / "comic-projects")
    project = _create_project(store)
    task_service = ComicTaskService(store)
    task = task_service.create_task(
        project_id=project.id,
        kind="import_project",
        target_id=project.id,
        input_payload={"source_text": "第一章：列车驶入暴风区。", "import_mode": "full_text"},
    )
    runner = ComicTaskRunner(store=store, task_service=task_service, workflow_service=FakeWorkflowService())

    result = runner.run_task(task)

    snapshot = store.get_project(project.id)
    assert len(snapshot.chapters) == 2
    assert result["chapters"][0]["title"] == "第一章"
    assert task_service.get_task(task.id).progress == 100


def test_scene_script_runner_creates_scenes_for_chapter(tmp_path: Path) -> None:
    store = ComicProjectStore(tmp_path / "comic-projects")
    project = _create_project(store)
    store.save_chapter(
        project.id,
        ComicChapter(
            id="chapter-1",
            project_id=project.id,
            title="第一章",
            source_text="列车驶入暴风区。",
            summary="暴风将至",
            order=1,
        ),
    )
    task_service = ComicTaskService(store)
    task = task_service.create_task(
        project_id=project.id,
        kind="generate_scene_script",
        target_id="chapter-1",
        input_payload={"chapter_id": "chapter-1"},
    )
    runner = ComicTaskRunner(store=store, task_service=task_service, workflow_service=FakeWorkflowService())

    result = runner.run_task(task)

    snapshot = store.get_project(project.id)
    assert len(snapshot.scenes) == 1
    assert snapshot.scenes[0].chapter_id == "chapter-1"
    assert result["scenes"][0]["title"] == "镜头一"


def test_render_scene_runner_writes_asset_and_updates_scene(tmp_path: Path) -> None:
    store = ComicProjectStore(tmp_path / "comic-projects")
    project = _create_project(store)
    store.save_chapter(
        project.id,
        ComicChapter(
            id="chapter-1",
            project_id=project.id,
            title="第一章",
            source_text="列车驶入暴风区。",
            summary="暴风将至",
            order=1,
        ),
    )
    store.save_scene(
        project.id,
        ComicScene(
            id="scene-1",
            project_id=project.id,
            chapter_id="chapter-1",
            title="镜头一",
            description="列车穿过雷暴云层。",
            prompt="赛博列车穿过雷暴云层",
            character_ids=(),
            order=1,
            assets=(),
        ),
    )
    task_service = ComicTaskService(store)
    task = task_service.create_task(
        project_id=project.id,
        kind="render_scene",
        target_id="scene-1",
        input_payload={"scene_id": "scene-1"},
    )
    runner = ComicTaskRunner(store=store, task_service=task_service, workflow_service=FakeWorkflowService())

    result = runner.run_task(task)

    snapshot = store.get_project(project.id)
    asset_path = tmp_path / "comic-projects" / project.id / "assets" / "scene-scene-1" / "asset-1.png"
    assert asset_path.is_file()
    assert len(snapshot.scenes[0].assets) == 1
    assert result["assets"][0]["relative_path"] == "scene-scene-1/asset-1.png"


def test_render_batch_runner_collects_errors_and_updates_progress(tmp_path: Path) -> None:
    store = ComicProjectStore(tmp_path / "comic-projects")
    project = _create_project(store)
    store.save_chapter(
        project.id,
        ComicChapter(
            id="chapter-1",
            project_id=project.id,
            title="第一章",
            source_text="列车驶入暴风区。",
            summary="暴风将至",
            order=1,
        ),
    )
    store.save_scene(
        project.id,
        ComicScene(
            id="scene-ok",
            project_id=project.id,
            chapter_id="chapter-1",
            title="镜头一",
            description="正常镜头",
            prompt="正常镜头 prompt",
            character_ids=(),
            order=1,
            assets=(),
        ),
    )
    store.save_scene(
        project.id,
        ComicScene(
            id="scene-fail",
            project_id=project.id,
            chapter_id="chapter-1",
            title="镜头二",
            description="失败镜头",
            prompt="失败镜头 prompt",
            character_ids=(),
            order=2,
            assets=(),
        ),
    )
    task_service = ComicTaskService(store)
    task = task_service.create_task(
        project_id=project.id,
        kind="render_batch",
        target_id="chapter-1",
        input_payload={"chapter_id": "chapter-1"},
    )
    runner = ComicTaskRunner(store=store, task_service=task_service, workflow_service=FakeWorkflowService())

    result = runner.run_task(task)

    assert len(result["assets"]) == 1
    assert result["errors"] == ["scene-fail: upstream render failed"]
    assert task_service.get_task(task.id).progress == 100
