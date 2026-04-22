from __future__ import annotations

import time
import uuid

from fastapi import HTTPException

from services.config import get_image_settings


IMAGE_MODELS = {"gpt-image-1", "gpt-image-2"}
IMAGE_RESPONSE_FORMATS = {"url", "b64_json"}
CHAT_ROLES = {"system", "user", "assistant"}


def is_image_chat_request(body: dict[str, object]) -> bool:
    model = str(body.get("model") or "").strip()
    modalities = body.get("modalities")
    if model in IMAGE_MODELS:
        return True
    if isinstance(modalities, list):
        normalized = {str(item or "").strip().lower() for item in modalities}
        return "image" in normalized
    return False


def extract_response_prompt(input_value: object) -> str:
    if isinstance(input_value, str):
        return input_value.strip()

    if isinstance(input_value, dict):
        role = str(input_value.get("role") or "").strip().lower()
        if role and role != "user":
            return ""
        return extract_prompt_from_message_content(input_value.get("content"))

    if not isinstance(input_value, list):
        return ""

    prompt_parts: list[str] = []
    for item in input_value:
        if isinstance(item, dict) and str(item.get("type") or "").strip() == "input_text":
            text = str(item.get("text") or "").strip()
            if text:
                prompt_parts.append(text)
            continue
        if not isinstance(item, dict):
            continue
        role = str(item.get("role") or "").strip().lower()
        if role and role != "user":
            continue
        prompt = extract_prompt_from_message_content(item.get("content"))
        if prompt:
            prompt_parts.append(prompt)
    return "\n".join(prompt_parts).strip()


def has_response_image_generation_tool(body: dict[str, object]) -> bool:
    tools = body.get("tools")
    if isinstance(tools, list):
        for tool in tools:
            if isinstance(tool, dict) and str(tool.get("type") or "").strip() == "image_generation":
                return True

    tool_choice = body.get("tool_choice")
    if isinstance(tool_choice, dict) and str(tool_choice.get("type") or "").strip() == "image_generation":
        return True
    return False


def extract_prompt_from_message_content(content: object) -> str:
    if isinstance(content, str):
        return content.strip()
    if not isinstance(content, list):
        return ""

    parts: list[str] = []
    for item in content:
        if not isinstance(item, dict):
            continue
        item_type = str(item.get("type") or "").strip()
        if item_type == "text":
            text = str(item.get("text") or "").strip()
            if text:
                parts.append(text)
            continue
        if item_type == "input_text":
            text = str(item.get("text") or item.get("input_text") or "").strip()
            if text:
                parts.append(text)
    return "\n".join(parts).strip()


def extract_image_from_message_content(content: object) -> tuple[bytes, str] | None:
    import base64 as b64

    if not isinstance(content, list):
        return None

    for item in content:
        if not isinstance(item, dict):
            continue
        item_type = str(item.get("type") or "").strip()
        if item_type == "image_url":
            url_obj = item.get("image_url") or item
            url = str(url_obj.get("url") or "") if isinstance(url_obj, dict) else str(url_obj)
            if url.startswith("data:"):
                header, _, data = url.partition(",")
                mime = header.split(";")[0].removeprefix("data:")
                return b64.b64decode(data), mime or "image/png"
        if item_type == "input_image":
            image_url = str(item.get("image_url") or "")
            if image_url.startswith("data:"):
                header, _, data = image_url.partition(",")
                mime = header.split(";")[0].removeprefix("data:")
                return b64.b64decode(data), mime or "image/png"
    return None


def extract_chat_image(body: dict[str, object]) -> tuple[bytes, str] | None:
    messages = body.get("messages")
    if not isinstance(messages, list):
        return None

    for message in reversed(messages):
        if not isinstance(message, dict):
            continue
        role = str(message.get("role") or "").strip().lower()
        if role != "user":
            continue
        result = extract_image_from_message_content(message.get("content"))
        if result:
            return result
    return None


def extract_chat_prompt(body: dict[str, object]) -> str:
    direct_prompt = str(body.get("prompt") or "").strip()
    if direct_prompt:
        return direct_prompt

    messages = body.get("messages")
    if not isinstance(messages, list):
        return ""

    prompt_parts: list[str] = []
    for message in messages:
        if not isinstance(message, dict):
            continue
        role = str(message.get("role") or "").strip().lower()
        if role != "user":
            continue
        prompt = extract_prompt_from_message_content(message.get("content"))
        if prompt:
            prompt_parts.append(prompt)

    return "\n".join(prompt_parts).strip()


def extract_text_chat_prompt(body: dict[str, object]) -> str:
    direct_prompt = str(body.get("prompt") or "").strip()
    if direct_prompt:
        return direct_prompt

    messages = body.get("messages")
    if not isinstance(messages, list):
        return ""

    prompt_parts: list[str] = []
    transcript_parts: list[str] = []
    for message in messages:
        if not isinstance(message, dict):
            continue
        role = str(message.get("role") or "").strip().lower()
        if role not in CHAT_ROLES:
            continue
        text = extract_prompt_from_message_content(message.get("content"))
        if not text:
            continue
        if role == "user":
            prompt_parts.append(text)
        transcript_parts.append(f"{role}: {text}")

    if len(transcript_parts) == 1 and len(prompt_parts) == 1:
        return prompt_parts[0]
    return "\n\n".join(transcript_parts).strip()


def parse_image_count(raw_value: object) -> int:
    try:
        value = int(raw_value or 1)
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail={"error": "n must be an integer"}) from exc
    max_count = get_image_settings().max_count_per_request
    if value < 1 or value > max_count:
        raise HTTPException(status_code=400, detail={"error": f"n must be between 1 and {max_count}"})
    return value


def parse_image_response_format(raw_value: object, *, default: str = "url") -> str:
    normalized = str(raw_value or default).strip().lower() or default
    if normalized not in IMAGE_RESPONSE_FORMATS:
        raise HTTPException(
            status_code=400,
            detail={"error": f"response_format must be one of: {', '.join(sorted(IMAGE_RESPONSE_FORMATS))}"},
        )
    return normalized


def extract_image_result_reference(item: dict[str, object]) -> str:
    url = str(item.get("url") or "").strip()
    if url:
        return url

    b64_json = str(item.get("b64_json") or "").strip()
    if b64_json:
        return f"data:image/png;base64,{b64_json}"
    return ""


def normalize_chat_image_item(item: dict[str, object]) -> dict[str, object]:
    normalized: dict[str, object] = {}
    url = str(item.get("url") or "").strip()
    b64_json = str(item.get("b64_json") or "").strip()
    revised_prompt = str(item.get("revised_prompt") or "").strip()

    if url:
        normalized["url"] = url
    if b64_json:
        normalized["b64_json"] = b64_json
    if revised_prompt:
        normalized["revised_prompt"] = revised_prompt
    return normalized


def build_chat_image_completion(
    model: str,
    prompt: str,
    image_result: dict[str, object],
) -> dict[str, object]:
    created = int(image_result.get("created") or time.time())
    image_items = image_result.get("data") if isinstance(image_result.get("data"), list) else []

    markdown_images = []
    normalized_images = []

    for index, item in enumerate(image_items, start=1):
        if not isinstance(item, dict):
            continue
        normalized_item = normalize_chat_image_item(item)
        if normalized_item:
            normalized_images.append(normalized_item)
        image_reference = extract_image_result_reference(item)
        if not image_reference:
            continue
        markdown_images.append(f"![image_{index}]({image_reference})")

    text_content = "\n\n".join(markdown_images) if markdown_images else "Image generation completed."

    return {
        "id": f"chatcmpl-{uuid.uuid4().hex}",
        "object": "chat.completion",
        "created": created,
        "model": model,
        "choices": [
            {
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": text_content,
                    "images": normalized_images,
                },
                "finish_reason": "stop",
            }
        ],
        "usage": {
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
        },
    }


def build_text_chat_completion(
    model: str,
    text: str,
) -> dict[str, object]:
    created = int(time.time())
    normalized_text = str(text or "").strip()
    return {
        "id": f"chatcmpl-{uuid.uuid4().hex}",
        "object": "chat.completion",
        "created": created,
        "model": model,
        "choices": [
            {
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": normalized_text,
                },
                "finish_reason": "stop",
            }
        ],
        "usage": {
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
        },
    }
