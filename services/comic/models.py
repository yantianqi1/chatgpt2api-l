from __future__ import annotations

from dataclasses import dataclass

JsonObject = dict[str, object]


def _string_tuple(values: object) -> tuple[str, ...]:
    if not isinstance(values, (list, tuple)):
        return ()
    return tuple(str(value).strip() for value in values if str(value).strip())


def _json_object(value: object) -> JsonObject:
    if isinstance(value, dict):
        return dict(value)
    return {}


@dataclass(frozen=True, slots=True)
class ComicProject:
    id: str
    title: str
    source_text: str
    style_prompt: str
    created_at: str
    updated_at: str

    @classmethod
    def from_dict(cls, payload: JsonObject) -> ComicProject:
        return cls(
            id=str(payload.get("id") or "").strip(),
            title=str(payload.get("title") or "").strip(),
            source_text=str(payload.get("source_text") or "").strip(),
            style_prompt=str(payload.get("style_prompt") or "").strip(),
            created_at=str(payload.get("created_at") or "").strip(),
            updated_at=str(payload.get("updated_at") or "").strip(),
        )


@dataclass(frozen=True, slots=True)
class CharacterProfile:
    id: str
    project_id: str
    name: str
    description: str
    appearance: str
    personality: str

    @classmethod
    def from_dict(cls, payload: JsonObject) -> CharacterProfile:
        return cls(
            id=str(payload.get("id") or "").strip(),
            project_id=str(payload.get("project_id") or "").strip(),
            name=str(payload.get("name") or "").strip(),
            description=str(payload.get("description") or "").strip(),
            appearance=str(payload.get("appearance") or "").strip(),
            personality=str(payload.get("personality") or "").strip(),
        )


@dataclass(frozen=True, slots=True)
class ComicChapter:
    id: str
    project_id: str
    title: str
    source_text: str
    summary: str
    order: int

    @classmethod
    def from_dict(cls, payload: JsonObject) -> ComicChapter:
        return cls(
            id=str(payload.get("id") or "").strip(),
            project_id=str(payload.get("project_id") or "").strip(),
            title=str(payload.get("title") or "").strip(),
            source_text=str(payload.get("source_text") or "").strip(),
            summary=str(payload.get("summary") or "").strip(),
            order=int(payload.get("order") or 0),
        )


@dataclass(frozen=True, slots=True)
class ComicAsset:
    id: str
    scene_id: str
    relative_path: str
    prompt: str
    created_at: str

    @classmethod
    def from_dict(cls, payload: JsonObject) -> ComicAsset:
        return cls(
            id=str(payload.get("id") or "").strip(),
            scene_id=str(payload.get("scene_id") or "").strip(),
            relative_path=str(payload.get("relative_path") or "").strip(),
            prompt=str(payload.get("prompt") or "").strip(),
            created_at=str(payload.get("created_at") or "").strip(),
        )


@dataclass(frozen=True, slots=True)
class ComicScene:
    id: str
    project_id: str
    chapter_id: str
    title: str
    description: str
    prompt: str
    character_ids: tuple[str, ...]
    order: int
    assets: tuple[ComicAsset, ...]

    @classmethod
    def from_dict(cls, payload: JsonObject) -> ComicScene:
        assets_payload = payload.get("assets") or []
        return cls(
            id=str(payload.get("id") or "").strip(),
            project_id=str(payload.get("project_id") or "").strip(),
            chapter_id=str(payload.get("chapter_id") or "").strip(),
            title=str(payload.get("title") or "").strip(),
            description=str(payload.get("description") or "").strip(),
            prompt=str(payload.get("prompt") or "").strip(),
            character_ids=_string_tuple(payload.get("character_ids")),
            order=int(payload.get("order") or 0),
            assets=tuple(
                ComicAsset.from_dict(_json_object(item))
                for item in assets_payload
                if isinstance(item, dict)
            ),
        )


@dataclass(frozen=True, slots=True)
class ComicTask:
    id: str
    project_id: str
    kind: str
    status: str
    target_id: str
    input_payload: JsonObject
    result_payload: JsonObject | None
    error: str | None
    created_at: str
    updated_at: str
    progress: int = 0

    @classmethod
    def from_dict(cls, payload: JsonObject) -> ComicTask:
        result_payload = payload.get("result_payload")
        return cls(
            id=str(payload.get("id") or "").strip(),
            project_id=str(payload.get("project_id") or "").strip(),
            kind=str(payload.get("kind") or "").strip(),
            status=str(payload.get("status") or "").strip(),
            target_id=str(payload.get("target_id") or "").strip(),
            input_payload=_json_object(payload.get("input_payload")),
            result_payload=_json_object(result_payload) if isinstance(result_payload, dict) else None,
            error=str(payload.get("error")).strip() if payload.get("error") is not None else None,
            created_at=str(payload.get("created_at") or "").strip(),
            updated_at=str(payload.get("updated_at") or "").strip(),
            progress=max(0, min(100, int(payload.get("progress") or 0))),
        )


@dataclass(frozen=True, slots=True)
class ComicProjectSnapshot:
    project: ComicProject
    characters: tuple[CharacterProfile, ...]
    chapters: tuple[ComicChapter, ...]
    scenes: tuple[ComicScene, ...]
    tasks: tuple[ComicTask, ...]
