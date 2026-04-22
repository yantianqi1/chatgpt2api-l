from __future__ import annotations

import json
import time
from collections.abc import Iterator


def _dump_sse_event(payload: dict[str, object]) -> str:
    return f"data: {json.dumps(payload, ensure_ascii=False, separators=(',', ':'))}\n\n"


def _chat_stream_meta(completion: dict[str, object]) -> tuple[str, int, str, str, str]:
    completion_id = str(completion.get("id") or "")
    created = int(completion.get("created") or time.time())
    model = str(completion.get("model") or "auto")

    choices = completion.get("choices")
    if not isinstance(choices, list) or not choices or not isinstance(choices[0], dict):
        return completion_id, created, model, "", "stop"

    message = choices[0].get("message")
    content = str(message.get("content") or "") if isinstance(message, dict) else ""
    finish_reason = str(choices[0].get("finish_reason") or "stop")
    return completion_id, created, model, content, finish_reason


def iter_chat_completion_sse(completion: dict[str, object]) -> Iterator[str]:
    completion_id, created, model, content, finish_reason = _chat_stream_meta(completion)
    base_chunk = {
        "id": completion_id,
        "object": "chat.completion.chunk",
        "created": created,
        "model": model,
    }

    yield _dump_sse_event(
        {
            **base_chunk,
            "choices": [{"index": 0, "delta": {"role": "assistant"}, "finish_reason": None}],
        }
    )
    if content:
        yield _dump_sse_event(
            {
                **base_chunk,
                "choices": [{"index": 0, "delta": {"content": content}, "finish_reason": None}],
            }
        )
    yield _dump_sse_event(
        {
            **base_chunk,
            "choices": [{"index": 0, "delta": {}, "finish_reason": finish_reason}],
        }
    )
    yield "data: [DONE]\n\n"


def iter_response_sse(response: dict[str, object]) -> Iterator[str]:
    yield _dump_sse_event(
        {
            "type": "response.completed",
            "response": response,
        }
    )
    yield "data: [DONE]\n\n"
