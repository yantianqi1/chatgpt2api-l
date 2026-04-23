from __future__ import annotations

import json
from importlib import import_module

import pytest

from services.comic.models import CharacterProfile


def _load_module(module_name: str):
    try:
        return import_module(module_name)
    except ModuleNotFoundError as exc:
        pytest.fail(f"missing module {module_name}: {exc}")


class FakeChatGPTService:
    def __init__(self, *, text_result: str = "{}", image_result: dict[str, object] | None = None) -> None:
        self.text_result = text_result
        self.image_result = image_result or {"created": 1, "data": [{"b64_json": "abc"}]}
        self.text_calls: list[tuple[str, str]] = []
        self.image_calls: list[tuple[str, str, int]] = []

    def generate_text_with_pool(self, prompt: str, model: str) -> str:
        self.text_calls.append((prompt, model))
        return self.text_result

    def generate_with_pool(self, prompt: str, model: str, n: int) -> dict[str, object]:
        self.image_calls.append((prompt, model, n))
        return self.image_result


def test_chapter_split_prompt_includes_source_text_and_strict_json() -> None:
    prompts = _load_module("services.comic.prompts")

    prompt = prompts.build_chapter_split_prompt("第一章：列车驶入暴风区。")

    assert "第一章：列车驶入暴风区。" in prompt
    assert "strict JSON" in prompt
    assert "\"chapters\"" in prompt


def test_scene_script_prompt_includes_only_relevant_characters() -> None:
    prompts = _load_module("services.comic.prompts")
    characters = [
        CharacterProfile(
            id="hero",
            project_id="project-1",
            name="阿青",
            description="主角",
            appearance="黑色短发",
            personality="冷静",
        ),
        CharacterProfile(
            id="villain",
            project_id="project-1",
            name="魇狐",
            description="反派",
            appearance="红色面具",
            personality="狡诈",
        ),
    ]

    prompt = prompts.build_scene_script_prompt(
        chapter_text="列车驶入暴风区。",
        style_prompt="赛博都市漫画",
        characters=characters,
        relevant_character_ids=("hero",),
    )

    assert "列车驶入暴风区。" in prompt
    assert "赛博都市漫画" in prompt
    assert "阿青" in prompt
    assert "黑色短发" in prompt
    assert "魇狐" not in prompt


def test_render_prompt_combines_style_scene_and_character_appearance() -> None:
    prompts = _load_module("services.comic.prompts")
    characters = [
        CharacterProfile(
            id="hero",
            project_id="project-1",
            name="阿青",
            description="主角",
            appearance="黑色短发，银色风衣",
            personality="冷静",
        )
    ]

    prompt = prompts.build_scene_render_prompt(
        scene_description="列车穿过雷暴云层。",
        style_prompt="赛博都市漫画",
        characters=characters,
    )

    assert "赛博都市漫画" in prompt
    assert "列车穿过雷暴云层。" in prompt
    assert "阿青" in prompt
    assert "黑色短发，银色风衣" in prompt


def test_workflow_methods_call_chatgpt_service_with_built_prompts() -> None:
    workflow_module = _load_module("services.comic.workflow")
    prompts = _load_module("services.comic.prompts")
    characters = [
        CharacterProfile(
            id="hero",
            project_id="project-1",
            name="阿青",
            description="主角",
            appearance="黑色短发，银色风衣",
            personality="冷静",
        )
    ]
    backend = FakeChatGPTService(
        text_result=json.dumps(
            {
                "chapters": [{"title": "第一章"}],
                "scenes": [{"title": "镜头一"}],
                "scene": {"title": "镜头一·修订"},
            },
            ensure_ascii=False,
        ),
        image_result={"created": 7, "data": [{"b64_json": "xyz"}]},
    )
    service = workflow_module.ComicWorkflowService(backend)

    chapters = service.split_chapters(source_text="第一章：列车驶入暴风区。", model="gpt-4.1")
    scenes = service.generate_scene_script(
        chapter_text="列车驶入暴风区。",
        style_prompt="赛博都市漫画",
        characters=characters,
        relevant_character_ids=("hero",),
        model="gpt-4.1",
    )
    rewritten_scene = service.rewrite_scene(
        scene_text="镜头一：列车进入云层。",
        feedback="强化速度感。",
        style_prompt="赛博都市漫画",
        characters=characters,
        model="gpt-4.1",
    )
    rendered = service.render_scene(
        scene_description="列车进入雷暴中心。",
        style_prompt="赛博都市漫画",
        characters=characters,
        model="gpt-image-1",
        n=2,
    )

    assert chapters == [{"title": "第一章"}]
    assert scenes == [{"title": "镜头一"}]
    assert rewritten_scene == {"title": "镜头一·修订"}
    assert rendered["data"] == [{"b64_json": "xyz"}]
    assert backend.text_calls == [
        (prompts.build_chapter_split_prompt("第一章：列车驶入暴风区。"), "gpt-4.1"),
        (
            prompts.build_scene_script_prompt(
                chapter_text="列车驶入暴风区。",
                style_prompt="赛博都市漫画",
                characters=characters,
                relevant_character_ids=("hero",),
            ),
            "gpt-4.1",
        ),
        (
            prompts.build_scene_rewrite_prompt(
                scene_text="镜头一：列车进入云层。",
                feedback="强化速度感。",
                style_prompt="赛博都市漫画",
                characters=characters,
            ),
            "gpt-4.1",
        ),
    ]
    assert backend.image_calls == [
        (
            prompts.build_scene_render_prompt(
                scene_description="列车进入雷暴中心。",
                style_prompt="赛博都市漫画",
                characters=characters,
            ),
            "gpt-image-1",
            2,
        )
    ]


def test_workflow_raises_domain_error_when_json_is_invalid() -> None:
    workflow_module = _load_module("services.comic.workflow")
    backend = FakeChatGPTService(text_result="not-json")
    service = workflow_module.ComicWorkflowService(backend)

    with pytest.raises(workflow_module.ComicWorkflowError, match="invalid JSON"):
        service.split_chapters(source_text="第一章：列车驶入暴风区。", model="gpt-4.1")
