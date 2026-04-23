from __future__ import annotations

from dataclasses import asdict
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query, Request, Response
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from services.comic.models import CharacterProfile, ComicAsset, ComicChapter, ComicScene

HTTP_CREATED = 201
HTTP_ACCEPTED = 202
HTTP_NO_CONTENT = 204


class ComicProjectCreateRequest(BaseModel):
    title: str
    source_text: str = ""
    style_prompt: str = ""


class ComicProjectUpdateRequest(BaseModel):
    title: str | None = None
    source_text: str | None = None
    style_prompt: str | None = None


class ComicImportRequest(BaseModel):
    source_text: str = ""
    import_mode: str = "full_text"


class ComicCharacterPayload(BaseModel):
    id: str
    name: str
    description: str = ""
    appearance: str = ""
    personality: str = ""


class ComicCharactersSaveRequest(BaseModel):
    characters: list[ComicCharacterPayload] = Field(default_factory=list)


class ComicChapterPayload(BaseModel):
    title: str
    source_text: str = ""
    summary: str = ""
    order: int = 0


class ComicAssetPayload(BaseModel):
    id: str
    scene_id: str
    relative_path: str
    prompt: str = ""
    created_at: str = ""


class ComicScenePayload(BaseModel):
    chapter_id: str
    title: str
    description: str = ""
    prompt: str = ""
    character_ids: list[str] = Field(default_factory=list)
    order: int = 0
    assets: list[ComicAssetPayload] = Field(default_factory=list)


def register_comic_routes(router: APIRouter) -> None:
    @router.get("/api/comic/projects")
    async def list_comic_projects(request: Request):
        return [asdict(project) for project in _store(request).list_projects()]

    @router.post("/api/comic/projects", status_code=HTTP_CREATED)
    async def create_comic_project(body: ComicProjectCreateRequest, request: Request):
        project = _store(request).create_project(
            title=body.title,
            source_text=body.source_text,
            style_prompt=body.style_prompt,
        )
        return asdict(project)

    @router.get("/api/comic/projects/{project_id}")
    async def get_comic_project(project_id: str, request: Request):
        snapshot = _project_snapshot(request, project_id)
        return _serialize_snapshot(snapshot)

    @router.patch("/api/comic/projects/{project_id}")
    async def update_comic_project(project_id: str, body: ComicProjectUpdateRequest, request: Request):
        try:
            project = _store(request).update_project(
                project_id,
                title=body.title,
                source_text=body.source_text,
                style_prompt=body.style_prompt,
            )
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail={"error": str(exc)}) from exc
        return asdict(project)

    @router.delete("/api/comic/projects/{project_id}", status_code=HTTP_NO_CONTENT)
    async def delete_comic_project(project_id: str, request: Request):
        try:
            _store(request).delete_project(project_id)
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail={"error": str(exc)}) from exc
        return Response(status_code=HTTP_NO_CONTENT)

    @router.post("/api/comic/projects/{project_id}/import", status_code=HTTP_ACCEPTED)
    async def import_comic_project(project_id: str, body: ComicImportRequest, request: Request):
        _ensure_project_exists(request, project_id)
        _store(request).update_project(project_id, source_text=body.source_text)
        task = _tasks(request).create_task(
            project_id=project_id,
            kind="import_project",
            target_id=project_id,
            input_payload=body.model_dump(),
        )
        return _task_response(task.id, task.status)

    @router.get("/api/comic/projects/{project_id}/characters")
    async def list_project_characters(project_id: str, request: Request):
        return [asdict(item) for item in _project_snapshot(request, project_id).characters]

    @router.post("/api/comic/projects/{project_id}/characters")
    async def save_project_characters(project_id: str, body: ComicCharactersSaveRequest, request: Request):
        characters = tuple(
            CharacterProfile(
                id=item.id,
                project_id=project_id,
                name=item.name,
                description=item.description,
                appearance=item.appearance,
                personality=item.personality,
            )
            for item in body.characters
        )
        _save_characters(request, project_id, characters)
        return [asdict(item) for item in characters]

    @router.get("/api/comic/projects/{project_id}/chapters")
    async def list_project_chapters(project_id: str, request: Request):
        return [asdict(item) for item in _project_snapshot(request, project_id).chapters]

    @router.patch("/api/comic/projects/{project_id}/chapters/{chapter_id}")
    async def save_project_chapter(project_id: str, chapter_id: str, body: ComicChapterPayload, request: Request):
        chapter = ComicChapter(
            id=chapter_id,
            project_id=project_id,
            title=body.title,
            source_text=body.source_text,
            summary=body.summary,
            order=body.order,
        )
        _save_chapter(request, project_id, chapter)
        return asdict(chapter)

    @router.post("/api/comic/projects/{project_id}/chapters/{chapter_id}/generate-script", status_code=HTTP_ACCEPTED)
    async def generate_chapter_script(project_id: str, chapter_id: str, request: Request):
        _ensure_project_exists(request, project_id)
        task = _tasks(request).create_task(
            project_id=project_id,
            kind="generate_scene_script",
            target_id=chapter_id,
            input_payload={"chapter_id": chapter_id},
        )
        return _task_response(task.id, task.status)

    @router.post("/api/comic/projects/{project_id}/chapters/{chapter_id}/render-batch", status_code=HTTP_ACCEPTED)
    async def render_chapter_batch(project_id: str, chapter_id: str, request: Request):
        _ensure_project_exists(request, project_id)
        task = _tasks(request).create_task(
            project_id=project_id,
            kind="render_batch",
            target_id=chapter_id,
            input_payload={"chapter_id": chapter_id},
        )
        return _task_response(task.id, task.status)

    @router.get("/api/comic/projects/{project_id}/scenes")
    async def list_project_scenes(project_id: str, request: Request, chapter_id: str | None = Query(default=None)):
        scenes = _project_snapshot(request, project_id).scenes
        if chapter_id is not None:
            scenes = tuple(item for item in scenes if item.chapter_id == chapter_id)
        return [asdict(item) for item in scenes]

    @router.patch("/api/comic/projects/{project_id}/scenes/{scene_id}")
    async def save_project_scene(project_id: str, scene_id: str, body: ComicScenePayload, request: Request):
        scene = ComicScene(
            id=scene_id,
            project_id=project_id,
            chapter_id=body.chapter_id,
            title=body.title,
            description=body.description,
            prompt=body.prompt,
            character_ids=tuple(body.character_ids),
            order=body.order,
            assets=tuple(
                ComicAsset(
                    id=item.id,
                    scene_id=item.scene_id,
                    relative_path=item.relative_path,
                    prompt=item.prompt,
                    created_at=item.created_at,
                )
                for item in body.assets
            ),
        )
        _save_scene(request, project_id, scene)
        return asdict(scene)

    @router.post("/api/comic/projects/{project_id}/scenes/{scene_id}/render", status_code=HTTP_ACCEPTED)
    async def render_scene(project_id: str, scene_id: str, request: Request):
        _ensure_project_exists(request, project_id)
        task = _tasks(request).create_task(
            project_id=project_id,
            kind="render_scene",
            target_id=scene_id,
            input_payload={"scene_id": scene_id},
        )
        return _task_response(task.id, task.status)

    @router.get("/api/comic/tasks")
    async def list_comic_tasks(request: Request, project_id: str | None = Query(default=None)):
        return [asdict(task) for task in _tasks(request).list_tasks(project_id=project_id)]

    @router.post("/api/comic/tasks/{task_id}/retry", status_code=HTTP_ACCEPTED)
    async def retry_comic_task(task_id: str, request: Request):
        try:
            task = _tasks(request).retry_task(task_id)
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail={"error": str(exc)}) from exc
        return _task_response(task.id, task.status)

    @router.get("/comic-assets/{project_id}/{asset_path:path}")
    async def get_comic_asset(project_id: str, asset_path: str, request: Request):
        asset_file = _resolve_asset_file(request, project_id, asset_path)
        if not asset_file.is_file():
            raise HTTPException(status_code=404, detail="Not Found")
        return FileResponse(asset_file)


def _store(request: Request):
    return request.app.state.comic_store


def _tasks(request: Request):
    return request.app.state.comic_task_service


def _project_snapshot(request: Request, project_id: str):
    try:
        return _store(request).get_project(project_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail={"error": str(exc)}) from exc


def _serialize_snapshot(snapshot) -> dict[str, object]:
    return {
        "project": asdict(snapshot.project),
        "characters": [asdict(item) for item in snapshot.characters],
        "chapters": [asdict(item) for item in snapshot.chapters],
        "scenes": [asdict(item) for item in snapshot.scenes],
        "tasks": [asdict(item) for item in snapshot.tasks],
    }


def _task_response(task_id: str, status: str) -> dict[str, object]:
    return {"task_id": task_id, "status": status}


def _ensure_project_exists(request: Request, project_id: str) -> None:
    _project_snapshot(request, project_id)


def _save_characters(request: Request, project_id: str, characters: tuple[CharacterProfile, ...]) -> None:
    try:
        _store(request).save_characters(project_id, list(characters))
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail={"error": str(exc)}) from exc


def _save_chapter(request: Request, project_id: str, chapter: ComicChapter) -> None:
    try:
        _store(request).save_chapter(project_id, chapter)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail={"error": str(exc)}) from exc


def _save_scene(request: Request, project_id: str, scene: ComicScene) -> None:
    try:
        _store(request).save_scene(project_id, scene)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail={"error": str(exc)}) from exc


def _resolve_asset_file(request: Request, project_id: str, asset_path: str) -> Path:
    asset_root = (_store(request).root_dir / project_id / "assets").resolve()
    candidate = (asset_root / asset_path).resolve()
    try:
        candidate.relative_to(asset_root)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="Not Found") from exc
    return candidate
