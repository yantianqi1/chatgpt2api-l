from __future__ import annotations

from typing import Callable, Iterable

from fastapi import HTTPException

from services.account_service import AccountService
from services.config import get_image_settings
from services.image_service import ImageGenerationError, edit_image_result, generate_image_result, is_token_invalid_error
from services.text_service import TextGenerationError, generate_text_result
from services.utils import (
    build_chat_image_completion,
    build_text_chat_completion,
    extract_chat_image,
    extract_chat_prompt,
    extract_image_result_reference,
    extract_text_chat_prompt,
    extract_image_from_message_content,
    extract_response_prompt,
    has_response_image_generation_tool,
    is_image_chat_request,
    parse_image_count,
    parse_image_response_format,
)


def _extract_response_image(input_value: object) -> tuple[bytes, str] | None:
    if isinstance(input_value, dict):
        return extract_image_from_message_content(input_value.get("content"))
    if not isinstance(input_value, list):
        return None
    for item in reversed(input_value):
        if isinstance(item, dict):
            if str(item.get("type") or "").strip() == "input_image":
                import base64 as b64
                image_url = str(item.get("image_url") or "")
                if image_url.startswith("data:"):
                    header, _, data = image_url.partition(",")
                    mime = header.split(";")[0].removeprefix("data:")
                    return b64.b64decode(data), mime or "image/png"
            content = item.get("content")
            if content:
                result = extract_image_from_message_content(content)
                if result:
                    return result
    return None


class ChatGPTService:
    def __init__(self, account_service: AccountService):
        self.account_service = account_service

    def _run_image_task(
        self,
        label: str,
        model: str,
        index: int,
        total: int,
        operation: Callable[[str], dict[str, object]],
        extra_log: str = "",
    ) -> dict[str, object] | None:
        retry_limit = get_image_settings().auto_retry_times + 1
        failed_attempts = 0

        while True:
            try:
                request_token = self.account_service.get_available_access_token()
            except RuntimeError as exc:
                print(f"[{label}] stop index={index}/{total} error={exc}")
                return None

            print(f"[{label}] start pooled token={request_token[:12]}... model={model} index={index}/{total}{extra_log}")
            try:
                result = operation(request_token)
                account = self.account_service.mark_image_result(request_token, success=True)
                print(
                    f"[{label}] success pooled token={request_token[:12]}... "
                    f"quota={account.get('quota') if account else 'unknown'} status={account.get('status') if account else 'unknown'}"
                )
                return result
            except ImageGenerationError as exc:
                account = self.account_service.mark_image_result(request_token, success=False)
                message = str(exc)
                print(
                    f"[{label}] fail pooled token={request_token[:12]}... "
                    f"error={message} quota={account.get('quota') if account else 'unknown'} status={account.get('status') if account else 'unknown'}"
                )
                if is_token_invalid_error(message):
                    self.account_service.remove_token(request_token)
                    print(f"[{label}] remove invalid token={request_token[:12]}...")
                    continue
                failed_attempts += 1
                if failed_attempts >= retry_limit:
                    return None
                print(f"[{label}] retry index={index}/{total} attempt={failed_attempts + 1}/{retry_limit}")

    @staticmethod
    def _append_image_items(result: dict[str, object], image_items: list[dict[str, object]]) -> int | None:
        created = result.get("created")
        data = result.get("data")
        if isinstance(data, list):
            image_items.extend(item for item in data if isinstance(item, dict))
        return int(created) if isinstance(created, int) else None

    def generate_with_pool(self, prompt: str, model: str, n: int, response_format: str = "url"):
        created = None
        image_items: list[dict[str, object]] = []

        for index in range(1, n + 1):
            result = self._run_image_task(
                label="image-generate",
                model=model,
                index=index,
                total=n,
                operation=lambda request_token: generate_image_result(request_token, prompt, model, response_format),
            )
            if result is None:
                continue
            next_created = self._append_image_items(result, image_items)
            if created is None and next_created is not None:
                created = next_created

        if not image_items:
            raise ImageGenerationError("image generation failed")

        return {
            "created": created,
            "data": image_items,
        }

    def edit_with_pool(
        self,
        prompt: str,
        images: Iterable[tuple[bytes, str, str]],
        model: str,
        n: int,
        response_format: str = "url",
    ):
        created = None
        image_items: list[dict[str, object]] = []
        normalized_images = list(images)
        if not normalized_images:
            raise ImageGenerationError("image is required")

        for index in range(1, n + 1):
            result = self._run_image_task(
                label="image-edit",
                model=model,
                index=index,
                total=n,
                operation=lambda request_token: edit_image_result(
                    request_token,
                    prompt,
                    normalized_images,
                    model,
                    response_format,
                ),
                extra_log=f" images={len(normalized_images)}",
            )
            if result is None:
                continue
            next_created = self._append_image_items(result, image_items)
            if created is None and next_created is not None:
                created = next_created

        if not image_items:
            raise ImageGenerationError("image edit failed")

        return {
            "created": created,
            "data": image_items,
        }

    def create_image_completion(self, body: dict[str, object]) -> dict[str, object]:
        if not is_image_chat_request(body):
            raise HTTPException(
                status_code=400,
                detail={"error": "only image generation requests are supported on this endpoint"},
            )

        model = str(body.get("model") or get_image_settings().default_model).strip() or get_image_settings().default_model
        n = parse_image_count(body.get("n"))
        response_format = parse_image_response_format(body.get("response_format"))
        prompt = extract_chat_prompt(body)
        if not prompt:
            raise HTTPException(status_code=400, detail={"error": "prompt is required"})

        image_info = extract_chat_image(body)
        try:
            if image_info:
                image_data, mime_type = image_info
                image_result = self.edit_with_pool(
                    prompt,
                    [(image_data, "image.png", mime_type)],
                    model,
                    n,
                    response_format,
                )
            else:
                image_result = self.generate_with_pool(prompt, model, n, response_format)
        except ImageGenerationError as exc:
            raise HTTPException(status_code=502, detail={"error": str(exc)}) from exc

        return build_chat_image_completion(model, prompt, image_result)

    def generate_text_with_pool(self, prompt: str, model: str) -> str:
        while True:
            try:
                request_token = self.account_service.get_chat_access_token()
            except RuntimeError as exc:
                print(f"[chat-text] stop error={exc}")
                raise TextGenerationError(str(exc)) from exc

            print(f"[chat-text] start pooled token={request_token[:12]}... model={model}")
            try:
                result = generate_text_result(request_token, prompt, model)
                account = self.account_service.mark_chat_result(request_token, success=True)
                print(
                    f"[chat-text] success pooled token={request_token[:12]}... "
                    f"status={account.get('status') if account else 'unknown'}"
                )
                return result
            except TextGenerationError as exc:
                account = self.account_service.mark_chat_result(request_token, success=False)
                message = str(exc)
                print(
                    f"[chat-text] fail pooled token={request_token[:12]}... "
                    f"error={message} status={account.get('status') if account else 'unknown'}"
                )
                if is_token_invalid_error(message):
                    self.account_service.remove_token(request_token)
                    print(f"[chat-text] remove invalid token={request_token[:12]}...")
                    continue
                raise

    def create_text_completion(self, body: dict[str, object]) -> dict[str, object]:
        model = str(body.get("model") or "").strip()
        prompt = extract_text_chat_prompt(body)
        if not prompt:
            raise HTTPException(status_code=400, detail={"error": "prompt is required"})

        try:
            text = self.generate_text_with_pool(prompt, model)
        except TextGenerationError as exc:
            raise HTTPException(status_code=502, detail={"error": str(exc)}) from exc

        return build_text_chat_completion(model or "auto", text)

    def create_chat_completion(self, body: dict[str, object]) -> dict[str, object]:
        if is_image_chat_request(body):
            return self.create_image_completion(body)
        return self.create_text_completion(body)

    def create_response(self, body: dict[str, object]) -> dict[str, object]:
        if not has_response_image_generation_tool(body):
            raise HTTPException(
                status_code=400,
                detail={"error": "only image_generation tool requests are supported on this endpoint"},
            )

        prompt = extract_response_prompt(body.get("input"))
        if not prompt:
            raise HTTPException(status_code=400, detail={"error": "input text is required"})

        image_info = _extract_response_image(body.get("input"))
        model = str(body.get("model") or "gpt-5").strip() or "gpt-5"
        default_image_model = get_image_settings().default_model
        response_format = parse_image_response_format(body.get("response_format"))
        try:
            if image_info:
                image_data, mime_type = image_info
                image_result = self.edit_with_pool(
                    prompt,
                    [(image_data, "image.png", mime_type)],
                    default_image_model,
                    1,
                    response_format,
                )
            else:
                image_result = self.generate_with_pool(prompt, default_image_model, 1, response_format)
        except ImageGenerationError as exc:
            raise HTTPException(status_code=502, detail={"error": str(exc)}) from exc

        image_items = image_result.get("data") if isinstance(image_result.get("data"), list) else []
        output = []
        for item in image_items:
            if not isinstance(item, dict):
                continue
            image_reference = extract_image_result_reference(item)
            if not image_reference:
                continue
            output.append(
                {
                    "id": f"ig_{len(output) + 1}",
                    "type": "image_generation_call",
                    "status": "completed",
                    "result": image_reference,
                    "revised_prompt": str(item.get("revised_prompt") or prompt).strip(),
                }
            )

        if not output:
            raise HTTPException(status_code=502, detail={"error": "image generation failed"})

        created = int(image_result.get("created") or 0)
        return {
            "id": f"resp_{created}",
            "object": "response",
            "created_at": created,
            "status": "completed",
            "error": None,
            "incomplete_details": None,
            "model": model,
            "output": output,
            "parallel_tool_calls": False,
        }
