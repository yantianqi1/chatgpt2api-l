from __future__ import annotations

import json
from collections.abc import Sequence
from typing import Protocol

from services.comic.models import CharacterProfile
from services.comic.prompts import (
    build_chapter_split_prompt,
    build_scene_render_prompt,
    build_scene_rewrite_prompt,
    build_scene_script_prompt,
)


class ComicGenerationBackend(Protocol):
    def generate_text_with_pool(self, prompt: str, model: str) -> str: ...

    def generate_with_pool(self, prompt: str, model: str, n: int) -> dict[str, object]: ...


class ComicWorkflowError(Exception):
    pass


class ComicWorkflowService:
    def __init__(self, backend: ComicGenerationBackend):
        self.backend = backend

    def split_chapters(self, *, source_text: str, model: str) -> list[dict[str, object]]:
        prompt = build_chapter_split_prompt(source_text)
        response_text = self.backend.generate_text_with_pool(prompt, model)
        return self._parse_list_response(response_text, key="chapters")

    def generate_scene_script(
        self,
        *,
        chapter_text: str,
        style_prompt: str,
        characters: Sequence[CharacterProfile],
        relevant_character_ids: Sequence[str],
        model: str,
    ) -> list[dict[str, object]]:
        prompt = build_scene_script_prompt(
            chapter_text=chapter_text,
            style_prompt=style_prompt,
            characters=characters,
            relevant_character_ids=relevant_character_ids,
        )
        response_text = self.backend.generate_text_with_pool(prompt, model)
        return self._parse_list_response(response_text, key="scenes")

    def rewrite_scene(
        self,
        *,
        scene_text: str,
        feedback: str,
        style_prompt: str,
        characters: Sequence[CharacterProfile],
        model: str,
    ) -> dict[str, object]:
        prompt = build_scene_rewrite_prompt(
            scene_text=scene_text,
            feedback=feedback,
            style_prompt=style_prompt,
            characters=characters,
        )
        response_text = self.backend.generate_text_with_pool(prompt, model)
        return self._parse_object_response(response_text, key="scene")

    def render_scene(
        self,
        *,
        scene_description: str,
        style_prompt: str,
        characters: Sequence[CharacterProfile],
        model: str,
        n: int,
    ) -> dict[str, object]:
        prompt = build_scene_render_prompt(
            scene_description=scene_description,
            style_prompt=style_prompt,
            characters=characters,
        )
        return self.backend.generate_with_pool(prompt, model, n)

    def _parse_list_response(self, response_text: str, *, key: str) -> list[dict[str, object]]:
        payload = self._parse_json_object(response_text, key=key)
        value = payload.get(key)
        if not isinstance(value, list):
            raise ComicWorkflowError(f"{key} must be a JSON array")
        return [dict(item) for item in value if isinstance(item, dict)]

    def _parse_object_response(self, response_text: str, *, key: str) -> dict[str, object]:
        payload = self._parse_json_object(response_text, key=key)
        value = payload.get(key)
        if not isinstance(value, dict):
            raise ComicWorkflowError(f"{key} must be a JSON object")
        return dict(value)

    def _parse_json_object(self, response_text: str, *, key: str) -> dict[str, object]:
        try:
            payload = json.loads(response_text)
        except json.JSONDecodeError as exc:
            raise ComicWorkflowError(f"invalid JSON for {key}: {exc.msg}") from exc
        if not isinstance(payload, dict):
            raise ComicWorkflowError(f"{key} response must be a JSON object")
        return dict(payload)
