from __future__ import annotations

import uuid

from services.account_service import account_service
from services.image_service import (
    USER_AGENT,
    _bootstrap,
    _chat_requirements,
    _generate_proof_token,
    _new_session,
    _parse_sse,
    _pow_config,
)

from curl_cffi.requests import Session


class TextGenerationError(Exception):
    pass


def _resolve_text_model(access_token: str, requested_model: str) -> str:
    model = str(requested_model or "").strip()
    if model:
        return model
    account = account_service.get_account(access_token) or {}
    return str(account.get("default_model_slug") or "auto").strip() or "auto"


def _send_text_conversation(
    session: Session,
    access_token: str,
    device_id: str,
    chat_token: str,
    proof_token: str | None,
    prompt: str,
    model: str,
):
    headers = {
        "Authorization": f"Bearer {access_token}",
        "accept": "text/event-stream",
        "accept-language": "zh-CN,zh;q=0.9,en;q=0.8",
        "content-type": "application/json",
        "oai-device-id": device_id,
        "oai-language": "zh-CN",
        "oai-client-build-number": "5955942",
        "oai-client-version": "prod-be885abbfcfe7b1f511e88b3003d9ee44757fbad",
        "origin": "https://chatgpt.com",
        "referer": "https://chatgpt.com/",
        "openai-sentinel-chat-requirements-token": chat_token,
    }
    if proof_token:
        headers["openai-sentinel-proof-token"] = proof_token

    response = session.post(
        "https://chatgpt.com/backend-api/conversation",
        headers=headers,
        json={
            "action": "next",
            "messages": [
                {
                    "id": str(uuid.uuid4()),
                    "author": {"role": "user"},
                    "content": {"content_type": "text", "parts": [prompt]},
                    "metadata": {"attachments": []},
                }
            ],
            "parent_message_id": str(uuid.uuid4()),
            "model": model,
            "history_and_training_disabled": False,
            "timezone_offset_min": -480,
            "timezone": "America/Los_Angeles",
            "conversation_mode": {"kind": "primary_assistant"},
            "conversation_origin": None,
            "force_paragen": False,
            "force_paragen_model_slug": "",
            "force_rate_limit": False,
            "force_use_sse": True,
            "paragen_cot_summary_display_override": "allow",
            "paragen_stream_type_override": None,
            "reset_rate_limits": False,
            "suggestions": [],
            "supported_encodings": [],
            "variant_purpose": "comparison_implicit",
            "websocket_request_id": str(uuid.uuid4()),
            "client_contextual_info": {
                "is_dark_mode": False,
                "time_since_loaded": 120,
                "page_height": 900,
                "page_width": 1440,
                "pixel_ratio": 1.0,
                "screen_height": 1080,
                "screen_width": 1920,
            },
        },
        stream=True,
        timeout=180,
    )
    if not response.ok:
        raise TextGenerationError(response.text[:400] or f"conversation failed: {response.status_code}")
    return response


def generate_text_result(access_token: str, prompt: str, model: str) -> str:
    normalized_prompt = str(prompt or "").strip()
    normalized_token = str(access_token or "").strip()
    if not normalized_prompt:
        raise TextGenerationError("prompt is required")
    if not normalized_token:
        raise TextGenerationError("token is required")

    session, fp = _new_session(normalized_token)
    try:
        upstream_model = _resolve_text_model(normalized_token, model)
        device_id = _bootstrap(session, fp)
        chat_token, pow_info = _chat_requirements(session, normalized_token, device_id)
        proof_token = None
        if pow_info.get("required"):
            proof_token = _generate_proof_token(
                seed=str(pow_info["seed"]),
                difficulty=str(pow_info["difficulty"]),
                user_agent=USER_AGENT,
                proof_config=_pow_config(USER_AGENT),
            )
        response = _send_text_conversation(
            session,
            normalized_token,
            device_id,
            chat_token,
            proof_token,
            normalized_prompt,
            upstream_model,
        )
        parsed = _parse_sse(response)
        text = str(parsed.get("text") or "").strip()
        if not text:
            raise TextGenerationError("no text returned from upstream")
        return text
    except Exception as exc:
        raise TextGenerationError(str(exc)) from exc
    finally:
        session.close()
