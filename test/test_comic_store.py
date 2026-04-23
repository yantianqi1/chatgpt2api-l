from __future__ import annotations

import json
from importlib import import_module
from pathlib import Path

import pytest

TEST_TIMESTAMP = "2026-04-23T00:00:00Z"


def _load_module(module_name: str):
    try:
        return import_module(module_name)
    except ModuleNotFoundError as exc:
        pytest.fail(f"missing module {module_name}: {exc}")


def _create_store(tmp_path: Path):
    module = _load_module("services.comic.store")
    return module.ComicProjectStore(tmp_path / "comic-projects")


def test_create_project_creates_project_file(tmp_path: Path) -> None:
    store = _create_store(tmp_path)

    project = store.create_project(
        title="银河列车",
        source_text="第一章：夜航开始。",
        style_prompt="赛博都市漫画",
    )

    project_file = tmp_path / "comic-projects" / project.id / "project.json"
    assert project_file.is_file()
    payload = json.loads(project_file.read_text(encoding="utf-8"))
    assert payload["id"] == project.id
    assert payload["title"] == "银河列车"
    assert payload["source_text"] == "第一章：夜航开始。"
    assert payload["style_prompt"] == "赛博都市漫画"


def test_save_helpers_write_predictable_subdirectories(tmp_path: Path) -> None:
    store = _create_store(tmp_path)
    models = _load_module("services.comic.models")
    project = store.create_project(
        title="银河列车",
        source_text="第一章：夜航开始。",
        style_prompt="赛博都市漫画",
    )

    character = models.CharacterProfile(
        id="char-1",
        project_id=project.id,
        name="阿青",
        description="年轻的列车护卫",
        appearance="黑色短发，银色风衣",
        personality="冷静克制",
    )
    chapter = models.ComicChapter(
        id="chapter-1",
        project_id=project.id,
        title="第一章",
        source_text="夜航开始，敌人潜入。",
        summary="列车进入风暴区。",
        order=1,
    )
    scene = models.ComicScene(
        id="scene-1",
        project_id=project.id,
        chapter_id=chapter.id,
        title="风暴前夜",
        description="列车驶入雷暴云层。",
        prompt="赛博列车穿过雷暴云层",
        character_ids=("char-1",),
        order=1,
        assets=(),
    )
    task = models.ComicTask(
        id="task-1",
        project_id=project.id,
        kind="render_scene",
        status="queued",
        target_id=scene.id,
        input_payload={"scene_id": scene.id},
        result_payload=None,
        error=None,
        created_at=TEST_TIMESTAMP,
        updated_at=TEST_TIMESTAMP,
    )

    store.save_characters(project.id, [character])
    store.save_chapter(project.id, chapter)
    store.save_scene(project.id, scene)
    store.save_task(project.id, task)

    base_dir = tmp_path / "comic-projects" / project.id
    assert (base_dir / "characters.json").is_file()
    assert (base_dir / "chapters" / "chapter-1.json").is_file()
    assert (base_dir / "scenes" / "scene-1.json").is_file()
    assert (base_dir / "tasks" / "task-1.json").is_file()

    loaded = store.get_project(project.id)
    assert loaded.project.id == project.id
    assert [item.id for item in loaded.characters] == ["char-1"]
    assert [item.id for item in loaded.chapters] == ["chapter-1"]
    assert [item.id for item in loaded.scenes] == ["scene-1"]
    assert [item.id for item in loaded.tasks] == ["task-1"]


def test_delete_project_removes_directory_tree(tmp_path: Path) -> None:
    store = _create_store(tmp_path)
    project = store.create_project(
        title="银河列车",
        source_text="第一章：夜航开始。",
        style_prompt="赛博都市漫画",
    )

    store.delete_project(project.id)

    assert not (tmp_path / "comic-projects" / project.id).exists()


def test_get_project_raises_clear_error_for_missing_project(tmp_path: Path) -> None:
    store = _create_store(tmp_path)

    with pytest.raises(FileNotFoundError, match="comic project not found: missing-project"):
        store.get_project("missing-project")
