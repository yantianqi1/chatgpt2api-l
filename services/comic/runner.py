from __future__ import annotations

import base64
from dataclasses import asdict, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Protocol

from services.comic.models import CharacterProfile, ComicAsset, ComicChapter, ComicProjectSnapshot, ComicScene, ComicTask
from services.comic.store import ComicProjectStore
from services.comic.tasks import ComicTaskService, STATUS_RUNNING

DEFAULT_TEXT_MODEL = "auto"
DEFAULT_IMAGE_MODEL = "gpt-image-1"
IMPORT_MODE_CHAPTER_TEXT = "chapter_text"
KIND_IMPORT_PROJECT = "import_project"
KIND_GENERATE_SCENE_SCRIPT = "generate_scene_script"
KIND_RENDER_SCENE = "render_scene"
KIND_RENDER_BATCH = "render_batch"
PERCENT_COMPLETE = 100
EMPTY_PROGRESS = 0
SUMMARY_PREVIEW_LENGTH = 80


class ComicWorkflowGateway(Protocol):
    def split_chapters(self, *, source_text: str, model: str) -> list[dict[str, object]]: ...

    def generate_scene_script(
        self,
        *,
        chapter_text: str,
        style_prompt: str,
        characters: tuple[CharacterProfile, ...],
        relevant_character_ids: tuple[str, ...],
        model: str,
    ) -> list[dict[str, object]]: ...

    def render_scene(
        self,
        *,
        scene_description: str,
        style_prompt: str,
        characters: tuple[CharacterProfile, ...],
        model: str,
        n: int,
    ) -> dict[str, object]: ...


class ComicTaskRunner:
    def __init__(
        self,
        *,
        store: ComicProjectStore,
        task_service: ComicTaskService,
        workflow_service: ComicWorkflowGateway,
        text_model: str = DEFAULT_TEXT_MODEL,
        image_model: str = DEFAULT_IMAGE_MODEL,
    ):
        self.store = store
        self.task_service = task_service
        self.workflow_service = workflow_service
        self.text_model = str(text_model or DEFAULT_TEXT_MODEL)
        self.image_model = str(image_model or DEFAULT_IMAGE_MODEL)

    def run_task(self, task: ComicTask) -> dict[str, object]:
        if task.kind == KIND_IMPORT_PROJECT:
            return self._import_project(task)
        if task.kind == KIND_GENERATE_SCENE_SCRIPT:
            return self._generate_scene_script(task)
        if task.kind == KIND_RENDER_SCENE:
            return self._render_scene(task)
        if task.kind == KIND_RENDER_BATCH:
            return self._render_batch(task)
        raise ValueError(f"unsupported comic task kind: {task.kind}")

    def _import_project(self, task: ComicTask) -> dict[str, object]:
        snapshot = self.store.get_project(task.project_id)
        source_text = str(task.input_payload.get("source_text") or snapshot.project.source_text).strip()
        if not source_text:
            raise ValueError("source_text is required for import")
        import_mode = str(task.input_payload.get("import_mode") or "").strip()
        if import_mode == IMPORT_MODE_CHAPTER_TEXT:
            chapter = self._build_single_chapter(snapshot, source_text)
            self.store.save_chapter(task.project_id, chapter)
            self._set_progress(task.id, PERCENT_COMPLETE)
            return {"chapters": [asdict(chapter)]}

        chapters = self.workflow_service.split_chapters(source_text=source_text, model=self.text_model)
        saved_chapters = []
        for index, payload in enumerate(chapters, start=1):
            chapter = self._build_chapter(snapshot.project.id, payload, index)
            self.store.save_chapter(task.project_id, chapter)
            saved_chapters.append(chapter)
        self._set_progress(task.id, PERCENT_COMPLETE)
        return {"chapters": [asdict(chapter) for chapter in saved_chapters]}

    def _generate_scene_script(self, task: ComicTask) -> dict[str, object]:
        snapshot = self.store.get_project(task.project_id)
        chapter = self._require_chapter(snapshot, task.target_id)
        scenes_payload = self.workflow_service.generate_scene_script(
            chapter_text=chapter.source_text,
            style_prompt=snapshot.project.style_prompt,
            characters=snapshot.characters,
            relevant_character_ids=tuple(character.id for character in snapshot.characters),
            model=self.text_model,
        )
        saved_scenes = []
        for index, payload in enumerate(scenes_payload, start=1):
            scene = self._build_scene(snapshot.project.id, chapter.id, payload, index)
            self.store.save_scene(task.project_id, scene)
            saved_scenes.append(scene)
        self._set_progress(task.id, PERCENT_COMPLETE)
        return {"scenes": [asdict(scene) for scene in saved_scenes]}

    def _render_scene(self, task: ComicTask) -> dict[str, object]:
        scene_with_assets = self._render_scene_internal(task.project_id, task.target_id)
        self._set_progress(task.id, PERCENT_COMPLETE)
        return {"assets": [asdict(asset) for asset in scene_with_assets.assets]}

    def _render_batch(self, task: ComicTask) -> dict[str, object]:
        snapshot = self.store.get_project(task.project_id)
        chapter = self._require_chapter(snapshot, task.target_id)
        chapter_scenes = [scene for scene in snapshot.scenes if scene.chapter_id == chapter.id]
        total = len(chapter_scenes)
        if total == 0:
            raise ValueError(f"no scenes found for chapter: {chapter.id}")
        all_assets: list[dict[str, object]] = []
        errors: list[str] = []
        for index, scene in enumerate(chapter_scenes, start=1):
            try:
                rendered_scene = self._render_scene_internal(task.project_id, scene.id)
                all_assets.extend(asdict(asset) for asset in rendered_scene.assets)
            except Exception as exc:
                errors.append(f"{scene.id}: {exc}")
            self._set_progress(task.id, int(index * PERCENT_COMPLETE / total))
        return {"assets": all_assets, "errors": errors}

    def _build_single_chapter(self, snapshot: ComicProjectSnapshot, source_text: str) -> ComicChapter:
        order = max((chapter.order for chapter in snapshot.chapters), default=EMPTY_PROGRESS) + 1
        return ComicChapter(
            id=f"chapter-{order}",
            project_id=snapshot.project.id,
            title=self._fallback_title(source_text, order),
            source_text=source_text,
            summary=source_text[:SUMMARY_PREVIEW_LENGTH].strip(),
            order=order,
        )

    def _build_chapter(self, project_id: str, payload: dict[str, object], index: int) -> ComicChapter:
        order = int(payload.get("order") or index)
        return ComicChapter(
            id=f"chapter-{order}",
            project_id=project_id,
            title=str(payload.get("title") or f"章节 {order}").strip(),
            source_text=str(payload.get("source_text") or "").strip(),
            summary=str(payload.get("summary") or "").strip(),
            order=order,
        )

    def _build_scene(self, project_id: str, chapter_id: str, payload: dict[str, object], index: int) -> ComicScene:
        order = int(payload.get("order") or index)
        return ComicScene(
            id=f"scene-{chapter_id}-{order}",
            project_id=project_id,
            chapter_id=chapter_id,
            title=str(payload.get("title") or f"镜头 {order}").strip(),
            description=str(payload.get("description") or "").strip(),
            prompt=str(payload.get("prompt") or "").strip(),
            character_ids=tuple(str(item).strip() for item in payload.get("character_ids") or [] if str(item).strip()),
            order=order,
            assets=(),
        )

    def _require_chapter(self, snapshot: ComicProjectSnapshot, chapter_id: str) -> ComicChapter:
        for chapter in snapshot.chapters:
            if chapter.id == chapter_id:
                return chapter
        raise FileNotFoundError(f"comic chapter not found: {chapter_id}")

    def _require_scene(self, snapshot: ComicProjectSnapshot, scene_id: str) -> ComicScene:
        for scene in snapshot.scenes:
            if scene.id == scene_id:
                return scene
        raise FileNotFoundError(f"comic scene not found: {scene_id}")

    def _scene_characters(self, snapshot: ComicProjectSnapshot, scene: ComicScene) -> tuple[CharacterProfile, ...]:
        if not scene.character_ids:
            return snapshot.characters
        return tuple(character for character in snapshot.characters if character.id in set(scene.character_ids))

    def _render_scene_internal(self, project_id: str, scene_id: str) -> ComicScene:
        snapshot = self.store.get_project(project_id)
        scene = self._require_scene(snapshot, scene_id)
        characters = self._scene_characters(snapshot, scene)
        result = self.workflow_service.render_scene(
            scene_description=scene.description or scene.prompt or scene.title,
            style_prompt=snapshot.project.style_prompt,
            characters=characters,
            model=self.image_model,
            n=1,
        )
        scene_with_assets = self._store_rendered_assets(snapshot.project.id, scene, result)
        self.store.save_scene(project_id, scene_with_assets)
        return scene_with_assets

    def _store_rendered_assets(self, project_id: str, scene: ComicScene, result: dict[str, object]) -> ComicScene:
        raw_assets = result.get("data")
        if not isinstance(raw_assets, list):
            raise ValueError("render_scene result must include a data array")
        saved_assets = list(scene.assets)
        asset_dir = self.store.root_dir / project_id / "assets" / f"scene-{scene.id}"
        asset_dir.mkdir(parents=True, exist_ok=True)
        for index, item in enumerate(raw_assets, start=1):
            if not isinstance(item, dict):
                continue
            encoded = str(item.get("b64_json") or "").strip()
            if not encoded:
                continue
            asset_id = f"asset-{len(saved_assets) + index}"
            asset_file = asset_dir / f"{asset_id}.png"
            asset_file.write_bytes(base64.b64decode(encoded))
            saved_assets.append(
                ComicAsset(
                    id=asset_id,
                    scene_id=scene.id,
                    relative_path=f"scene-{scene.id}/{asset_id}.png",
                    prompt=str(item.get("revised_prompt") or scene.prompt or scene.description).strip(),
                    created_at=self._timestamp(),
                )
            )
        return replace(scene, assets=tuple(saved_assets))

    def _set_progress(self, task_id: str, progress: int) -> None:
        self.task_service.update_task(
            task_id,
            status=STATUS_RUNNING,
            progress=progress,
        )

    def _fallback_title(self, source_text: str, order: int) -> str:
        first_line = next((line.strip() for line in source_text.splitlines() if line.strip()), "")
        return first_line[:SUMMARY_PREVIEW_LENGTH] or f"导入章节 {order}"

    def _timestamp(self) -> str:
        return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
