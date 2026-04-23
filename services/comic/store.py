from __future__ import annotations

import json
from dataclasses import asdict, replace
from datetime import datetime, timezone
from pathlib import Path
from shutil import rmtree
from uuid import uuid4

from services.comic.models import (
    CharacterProfile,
    ComicChapter,
    ComicProject,
    ComicProjectSnapshot,
    ComicScene,
    ComicTask,
)
from services.config import config

JSON_INDENT = 2


def _utc_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _normalize_identifier(value: str, *, name: str) -> str:
    identifier = str(value or "").strip()
    if not identifier or Path(identifier).name != identifier:
        raise ValueError(f"{name} is invalid")
    return identifier


class ComicProjectStore:
    def __init__(self, root_dir: Path | None = None):
        self.root_dir = Path(root_dir or config.comic_projects_dir)
        self.root_dir.mkdir(parents=True, exist_ok=True)

    def list_projects(self) -> list[ComicProject]:
        project_files = sorted(self.root_dir.glob("*/project.json"))
        return [ComicProject.from_dict(self._read_json_object(path, name="project")) for path in project_files]

    def create_project(self, *, title: str, source_text: str, style_prompt: str) -> ComicProject:
        timestamp = _utc_timestamp()
        project = ComicProject(
            id=uuid4().hex,
            title=str(title or "").strip(),
            source_text=str(source_text or "").strip(),
            style_prompt=str(style_prompt or "").strip(),
            created_at=timestamp,
            updated_at=timestamp,
        )
        self._write_json(self._project_file(project.id), asdict(project))
        return project

    def get_project(self, project_id: str) -> ComicProjectSnapshot:
        project_key = _normalize_identifier(project_id, name="project_id")
        project_dir = self._require_project_dir(project_key)
        return ComicProjectSnapshot(
            project=self._load_project(project_key),
            characters=self._load_characters(project_dir),
            chapters=self._load_chapters(project_dir),
            scenes=self._load_scenes(project_dir),
            tasks=self._load_tasks(project_dir),
        )

    def update_project(
        self,
        project_id: str,
        *,
        title: str | None = None,
        source_text: str | None = None,
        style_prompt: str | None = None,
    ) -> ComicProject:
        project_key = _normalize_identifier(project_id, name="project_id")
        current = self._load_project(project_key)
        updated = replace(
            current,
            title=current.title if title is None else str(title).strip(),
            source_text=current.source_text if source_text is None else str(source_text).strip(),
            style_prompt=current.style_prompt if style_prompt is None else str(style_prompt).strip(),
            updated_at=_utc_timestamp(),
        )
        self._write_json(self._project_file(project_key), asdict(updated))
        return updated

    def save_characters(self, project_id: str, characters: list[CharacterProfile]) -> None:
        project_key = _normalize_identifier(project_id, name="project_id")
        self._require_project_dir(project_key)
        payload = [asdict(character) for character in characters]
        self._write_json(self._project_dir(project_key) / "characters.json", payload)
        self._touch_project(project_key)

    def save_chapter(self, project_id: str, chapter: ComicChapter) -> None:
        project_key = _normalize_identifier(project_id, name="project_id")
        chapter_key = _normalize_identifier(chapter.id, name="chapter_id")
        self._require_project_dir(project_key)
        self._write_json(self._project_dir(project_key) / "chapters" / f"{chapter_key}.json", asdict(chapter))
        self._touch_project(project_key)

    def save_scene(self, project_id: str, scene: ComicScene) -> None:
        project_key = _normalize_identifier(project_id, name="project_id")
        scene_key = _normalize_identifier(scene.id, name="scene_id")
        self._require_project_dir(project_key)
        self._write_json(self._project_dir(project_key) / "scenes" / f"{scene_key}.json", asdict(scene))
        self._touch_project(project_key)

    def save_task(self, project_id: str, task: ComicTask) -> None:
        project_key = _normalize_identifier(project_id, name="project_id")
        task_key = _normalize_identifier(task.id, name="task_id")
        self._require_project_dir(project_key)
        self._write_json(self._project_dir(project_key) / "tasks" / f"{task_key}.json", asdict(task))
        self._touch_project(project_key)

    def delete_project(self, project_id: str) -> None:
        project_key = _normalize_identifier(project_id, name="project_id")
        project_dir = self._require_project_dir(project_key)
        rmtree(project_dir)

    def _load_project(self, project_id: str) -> ComicProject:
        payload = self._read_json_object(self._project_file(project_id), name="project")
        return ComicProject.from_dict(payload)

    def _load_characters(self, project_dir: Path) -> tuple[CharacterProfile, ...]:
        payload = self._read_json_array(project_dir / "characters.json", default=[])
        return tuple(CharacterProfile.from_dict(item) for item in payload)

    def _load_chapters(self, project_dir: Path) -> tuple[ComicChapter, ...]:
        return tuple(
            sorted(
                self._load_directory_items(project_dir / "chapters", ComicChapter.from_dict),
                key=lambda chapter: (chapter.order, chapter.id),
            )
        )

    def _load_scenes(self, project_dir: Path) -> tuple[ComicScene, ...]:
        return tuple(
            sorted(
                self._load_directory_items(project_dir / "scenes", ComicScene.from_dict),
                key=lambda scene: (scene.order, scene.id),
            )
        )

    def _load_tasks(self, project_dir: Path) -> tuple[ComicTask, ...]:
        return tuple(
            sorted(
                self._load_directory_items(project_dir / "tasks", ComicTask.from_dict),
                key=lambda task: (task.created_at, task.id),
            )
        )

    def _load_directory_items(self, directory: Path, loader):
        if not directory.exists():
            return []
        items = []
        for path in sorted(directory.glob("*.json")):
            items.append(loader(self._read_json_object(path, name=path.stem)))
        return items

    def _touch_project(self, project_id: str) -> None:
        current = self._load_project(project_id)
        updated = replace(current, updated_at=_utc_timestamp())
        self._write_json(self._project_file(project_id), asdict(updated))

    def _project_dir(self, project_id: str) -> Path:
        project_key = _normalize_identifier(project_id, name="project_id")
        return self.root_dir / project_key

    def _project_file(self, project_id: str) -> Path:
        return self._project_dir(project_id) / "project.json"

    def _require_project_dir(self, project_id: str) -> Path:
        project_dir = self._project_dir(project_id)
        if not project_dir.is_dir():
            raise FileNotFoundError(f"comic project not found: {project_id}")
        return project_dir

    def _read_json_object(self, path: Path, *, name: str) -> dict[str, object]:
        if not path.exists():
            raise FileNotFoundError(f"{name} file not found: {path}")
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError(f"{name} must be a JSON object")
        return payload

    def _read_json_array(self, path: Path, *, default: list[dict[str, object]]) -> list[dict[str, object]]:
        if not path.exists():
            return default
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, list):
            raise ValueError(f"{path.name} must be a JSON array")
        return [dict(item) for item in payload if isinstance(item, dict)]

    def _write_json(self, path: Path, payload: object) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        content = json.dumps(payload, ensure_ascii=False, indent=JSON_INDENT) + "\n"
        path.write_text(content, encoding="utf-8")
