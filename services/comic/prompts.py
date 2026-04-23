from __future__ import annotations

from collections.abc import Sequence

from services.comic.models import CharacterProfile


def _format_character_block(characters: Sequence[CharacterProfile]) -> str:
    if not characters:
        return "No character context."
    blocks = []
    for character in characters:
        blocks.append(
            f"- {character.name}\n"
            f"  description: {character.description}\n"
            f"  appearance: {character.appearance}\n"
            f"  personality: {character.personality}"
        )
    return "\n".join(blocks)


def _select_relevant_characters(
    characters: Sequence[CharacterProfile],
    relevant_character_ids: Sequence[str],
) -> tuple[CharacterProfile, ...]:
    relevant_ids = {str(character_id).strip() for character_id in relevant_character_ids if str(character_id).strip()}
    if not relevant_ids:
        return tuple(characters)
    return tuple(character for character in characters if character.id in relevant_ids)


def build_chapter_split_prompt(source_text: str) -> str:
    normalized_source = str(source_text or "").strip()
    return (
        "Split the source novel excerpt into comic-ready chapters.\n"
        "Return strict JSON with the shape {\"chapters\": [...]}.\n"
        "Each chapter item must include title, summary, source_text, and order.\n"
        "Do not include markdown fences, explanations, or extra keys.\n"
        f"Source text:\n{normalized_source}"
    )


def build_scene_script_prompt(
    *,
    chapter_text: str,
    style_prompt: str,
    characters: Sequence[CharacterProfile],
    relevant_character_ids: Sequence[str],
) -> str:
    relevant_characters = _select_relevant_characters(characters, relevant_character_ids)
    return (
        "Create a comic scene script for the chapter below.\n"
        "Return strict JSON with the shape {\"scenes\": [...]}.\n"
        "Each scene item must include title, description, prompt, character_ids, and order.\n"
        f"Style prompt:\n{str(style_prompt or '').strip()}\n\n"
        f"Chapter text:\n{str(chapter_text or '').strip()}\n\n"
        f"Relevant characters:\n{_format_character_block(relevant_characters)}"
    )


def build_scene_rewrite_prompt(
    *,
    scene_text: str,
    feedback: str,
    style_prompt: str,
    characters: Sequence[CharacterProfile],
) -> str:
    return (
        "Rewrite the comic scene according to the feedback.\n"
        "Return strict JSON with the shape {\"scene\": {...}}.\n"
        "The scene object must include title, description, prompt, and character_ids.\n"
        f"Style prompt:\n{str(style_prompt or '').strip()}\n\n"
        f"Current scene:\n{str(scene_text or '').strip()}\n\n"
        f"Feedback:\n{str(feedback or '').strip()}\n\n"
        f"Character context:\n{_format_character_block(characters)}"
    )


def build_scene_render_prompt(
    *,
    scene_description: str,
    style_prompt: str,
    characters: Sequence[CharacterProfile],
) -> str:
    return (
        f"Global style: {str(style_prompt or '').strip()}\n"
        f"Scene description: {str(scene_description or '').strip()}\n"
        f"Character appearance guide:\n{_format_character_block(characters)}\n"
        "Generate a single cohesive comic panel prompt."
    )
