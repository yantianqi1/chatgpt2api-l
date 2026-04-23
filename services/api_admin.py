from __future__ import annotations

from fastapi import APIRouter, File, Form, Header, HTTPException, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ConfigDict, Field

from services.account_service import account_service
from services.chatgpt_service import ChatGPTService
from services.config import (
    IMAGE_COUNT_LIMIT,
    IMAGE_RETRY_LIMIT,
    IMAGE_TIMEOUT_LIMIT,
    get_image_settings,
    update_image_settings,
)
from services.cpa_service import cpa_config, cpa_import_service, list_remote_files
from services.image_errors import ImageGenerationError, image_generation_status_code
from services.streaming import iter_chat_completion_sse, iter_response_sse
from services.utils import parse_image_count, parse_image_response_format


class ImageGenerationRequest(BaseModel):
    prompt: str = Field(..., min_length=1)
    model: str = "gpt-image-2"
    n: int = Field(default=1, ge=1)
    response_format: str = "url"
    history_disabled: bool = True


class ImageSettingsUpdateRequest(BaseModel):
    default_model: str | None = None
    max_count_per_request: int | None = Field(default=None, ge=1, le=IMAGE_COUNT_LIMIT)
    auto_retry_times: int | None = Field(default=None, ge=0, le=IMAGE_RETRY_LIMIT)
    request_timeout_seconds: int | None = Field(default=None, ge=0, le=IMAGE_TIMEOUT_LIMIT)


class AccountCreateRequest(BaseModel):
    tokens: list[str] = Field(default_factory=list)


class AccountDeleteRequest(BaseModel):
    tokens: list[str] = Field(default_factory=list)


class AccountRefreshRequest(BaseModel):
    access_tokens: list[str] = Field(default_factory=list)


class AccountUpdateRequest(BaseModel):
    access_token: str = Field(default="")
    type: str | None = None
    status: str | None = None
    quota: int | None = None


class ChatCompletionRequest(BaseModel):
    model_config = ConfigDict(extra="allow")

    model: str | None = None
    prompt: str | None = None
    n: int | None = None
    stream: bool | None = None
    modalities: list[str] | None = None
    messages: list[dict[str, object]] | None = None


class ResponseCreateRequest(BaseModel):
    model_config = ConfigDict(extra="allow")

    model: str | None = None
    input: object | None = None
    tools: list[dict[str, object]] | None = None
    tool_choice: object | None = None
    stream: bool | None = None


class CPAPoolCreateRequest(BaseModel):
    name: str = ""
    base_url: str = ""
    secret_key: str = ""


class CPAPoolUpdateRequest(BaseModel):
    name: str | None = None
    base_url: str | None = None
    secret_key: str | None = None


class CPAImportRequest(BaseModel):
    names: list[str] = Field(default_factory=list)


def build_model_item(model_id: str) -> dict[str, object]:
    return {
        "id": model_id,
        "object": "model",
        "created": 0,
        "owned_by": "chatgpt2api",
    }


def sanitize_cpa_pool(pool: dict | None) -> dict | None:
    if not isinstance(pool, dict):
        return None
    return {key: value for key, value in pool.items() if key != "secret_key"}


def sanitize_cpa_pools(pools: list[dict]) -> list[dict]:
    return [sanitized for pool in pools if (sanitized := sanitize_cpa_pool(pool)) is not None]


def serialize_image_settings() -> dict[str, object]:
    settings = get_image_settings()
    return {
        "default_model": settings.default_model,
        "max_count_per_request": settings.max_count_per_request,
        "auto_retry_times": settings.auto_retry_times,
        "request_timeout_seconds": settings.request_timeout_seconds,
    }


async def _read_uploaded_images(image: list[UploadFile]) -> list[tuple[bytes, str, str]]:
    images: list[tuple[bytes, str, str]] = []
    for upload in image:
        image_data = await upload.read()
        if not image_data:
            raise HTTPException(status_code=400, detail={"error": "image file is empty"})
        images.append((image_data, upload.filename or "image.png", upload.content_type or "image/png"))
    return images


def register_model_routes(router: APIRouter) -> None:
    @router.get("/v1/models")
    async def list_models():
        return {
            "object": "list",
            "data": [build_model_item("gpt-image-1"), build_model_item("gpt-image-2")],
        }


def register_meta_routes(router: APIRouter, *, app_version: str, require_auth_key) -> None:
    @router.post("/auth/login")
    async def login(authorization: str | None = Header(default=None)):
        require_auth_key(authorization)
        return {"ok": True, "version": app_version}

    @router.get("/version")
    async def get_version():
        return {"version": app_version}


def register_account_routes(router: APIRouter, *, require_auth_key) -> None:
    @router.get("/api/accounts")
    async def get_accounts(authorization: str | None = Header(default=None)):
        require_auth_key(authorization)
        return {"items": account_service.list_accounts()}

    @router.post("/api/accounts")
    async def create_accounts(body: AccountCreateRequest, authorization: str | None = Header(default=None)):
        require_auth_key(authorization)
        tokens = [str(token or "").strip() for token in body.tokens if str(token or "").strip()]
        if not tokens:
            raise HTTPException(status_code=400, detail={"error": "tokens is required"})
        result = account_service.add_accounts(tokens)
        refresh_result = account_service.refresh_accounts(tokens)
        return {
            **result,
            "refreshed": refresh_result.get("refreshed", 0),
            "errors": refresh_result.get("errors", []),
            "items": refresh_result.get("items", result.get("items", [])),
        }

    @router.delete("/api/accounts")
    async def delete_accounts(body: AccountDeleteRequest, authorization: str | None = Header(default=None)):
        require_auth_key(authorization)
        tokens = [str(token or "").strip() for token in body.tokens if str(token or "").strip()]
        if not tokens:
            raise HTTPException(status_code=400, detail={"error": "tokens is required"})
        return account_service.delete_accounts(tokens)

    @router.post("/api/accounts/refresh")
    async def refresh_accounts(body: AccountRefreshRequest, authorization: str | None = Header(default=None)):
        require_auth_key(authorization)
        access_tokens = [str(token or "").strip() for token in body.access_tokens if str(token or "").strip()]
        if not access_tokens:
            access_tokens = account_service.list_tokens()
        if not access_tokens:
            raise HTTPException(status_code=400, detail={"error": "access_tokens is required"})
        return account_service.refresh_accounts(access_tokens)

    @router.post("/api/accounts/update")
    async def update_account(body: AccountUpdateRequest, authorization: str | None = Header(default=None)):
        require_auth_key(authorization)
        access_token = str(body.access_token or "").strip()
        if not access_token:
            raise HTTPException(status_code=400, detail={"error": "access_token is required"})
        updates = {key: value for key, value in body.model_dump().items() if key != "access_token" and value is not None}
        if not updates:
            raise HTTPException(status_code=400, detail={"error": "no updates provided"})
        account = account_service.update_account(access_token, updates)
        if account is None:
            raise HTTPException(status_code=404, detail={"error": "account not found"})
        return {"item": account, "items": account_service.list_accounts()}

    @router.get("/api/image/settings")
    async def get_image_runtime_settings(authorization: str | None = Header(default=None)):
        require_auth_key(authorization)
        return serialize_image_settings()

    @router.post("/api/image/settings")
    async def save_image_runtime_settings(
        body: ImageSettingsUpdateRequest,
        authorization: str | None = Header(default=None),
    ):
        require_auth_key(authorization)
        updates = body.model_dump(exclude_none=True)
        if not updates:
            raise HTTPException(status_code=400, detail={"error": "no updates provided"})
        update_image_settings(updates)
        return serialize_image_settings()


def register_openai_routes(router: APIRouter, *, chatgpt_service: ChatGPTService, require_auth_key) -> None:
    @router.post("/v1/images/generations")
    async def generate_images(body: ImageGenerationRequest, authorization: str | None = Header(default=None)):
        require_auth_key(authorization)
        count = parse_image_count(body.n)
        response_format = parse_image_response_format(body.response_format, default="url")
        try:
            return await run_in_threadpool(
                chatgpt_service.generate_with_pool,
                body.prompt,
                body.model,
                count,
                response_format,
            )
        except ImageGenerationError as exc:
            raise HTTPException(status_code=image_generation_status_code(exc), detail={"error": str(exc)}) from exc

    @router.post("/v1/images/edits")
    async def edit_images(
        authorization: str | None = Header(default=None),
        image: list[UploadFile] = File(...),
        prompt: str = Form(...),
        model: str = Form(default="gpt-image-2"),
        n: int = Form(default=1),
        response_format: str = Form(default="url"),
    ):
        require_auth_key(authorization)
        count = parse_image_count(n)
        normalized_response_format = parse_image_response_format(response_format, default="url")
        images = await _read_uploaded_images(image)
        try:
            return await run_in_threadpool(
                chatgpt_service.edit_with_pool,
                prompt,
                images,
                model,
                count,
                normalized_response_format,
            )
        except ImageGenerationError as exc:
            raise HTTPException(status_code=image_generation_status_code(exc), detail={"error": str(exc)}) from exc

    @router.post("/v1/chat/completions")
    async def create_chat_completion(body: ChatCompletionRequest, authorization: str | None = Header(default=None)):
        require_auth_key(authorization)
        payload = body.model_dump(mode="python")
        completion = await run_in_threadpool(chatgpt_service.create_chat_completion, payload)
        if bool(payload.get("stream")):
            return StreamingResponse(
                iter_chat_completion_sse(completion),
                media_type="text/event-stream",
                headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
            )
        return completion

    @router.post("/v1/responses")
    async def create_response(body: ResponseCreateRequest, authorization: str | None = Header(default=None)):
        require_auth_key(authorization)
        payload = body.model_dump(mode="python")
        response = await run_in_threadpool(chatgpt_service.create_response, payload)
        if bool(payload.get("stream")):
            return StreamingResponse(
                iter_response_sse(response),
                media_type="text/event-stream",
                headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
            )
        return response


def register_cpa_routes(router: APIRouter, *, require_auth_key) -> None:
    @router.get("/api/cpa/pools")
    async def list_cpa_pools(authorization: str | None = Header(default=None)):
        require_auth_key(authorization)
        return {"pools": sanitize_cpa_pools(cpa_config.list_pools())}

    @router.post("/api/cpa/pools")
    async def create_cpa_pool(body: CPAPoolCreateRequest, authorization: str | None = Header(default=None)):
        require_auth_key(authorization)
        if not body.base_url.strip():
            raise HTTPException(status_code=400, detail={"error": "base_url is required"})
        if not body.secret_key.strip():
            raise HTTPException(status_code=400, detail={"error": "secret_key is required"})
        pool = cpa_config.add_pool(name=body.name, base_url=body.base_url, secret_key=body.secret_key)
        return {"pool": sanitize_cpa_pool(pool), "pools": sanitize_cpa_pools(cpa_config.list_pools())}

    @router.post("/api/cpa/pools/{pool_id}")
    async def update_cpa_pool(
        pool_id: str,
        body: CPAPoolUpdateRequest,
        authorization: str | None = Header(default=None),
    ):
        require_auth_key(authorization)
        pool = cpa_config.update_pool(pool_id, body.model_dump(exclude_none=True))
        if pool is None:
            raise HTTPException(status_code=404, detail={"error": "pool not found"})
        return {"pool": sanitize_cpa_pool(pool), "pools": sanitize_cpa_pools(cpa_config.list_pools())}

    @router.delete("/api/cpa/pools/{pool_id}")
    async def delete_cpa_pool(pool_id: str, authorization: str | None = Header(default=None)):
        require_auth_key(authorization)
        if not cpa_config.delete_pool(pool_id):
            raise HTTPException(status_code=404, detail={"error": "pool not found"})
        return {"pools": sanitize_cpa_pools(cpa_config.list_pools())}

    @router.get("/api/cpa/pools/{pool_id}/files")
    async def cpa_pool_files(pool_id: str, authorization: str | None = Header(default=None)):
        require_auth_key(authorization)
        pool = cpa_config.get_pool(pool_id)
        if pool is None:
            raise HTTPException(status_code=404, detail={"error": "pool not found"})
        files = await run_in_threadpool(list_remote_files, pool)
        return {"pool_id": pool_id, "files": files}

    @router.post("/api/cpa/pools/{pool_id}/import")
    async def cpa_pool_import(pool_id: str, body: CPAImportRequest, authorization: str | None = Header(default=None)):
        require_auth_key(authorization)
        pool = cpa_config.get_pool(pool_id)
        if pool is None:
            raise HTTPException(status_code=404, detail={"error": "pool not found"})
        try:
            job = cpa_import_service.start_import(pool, body.names)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail={"error": str(exc)}) from exc
        return {"import_job": job}

    @router.get("/api/cpa/pools/{pool_id}/import")
    async def cpa_pool_import_progress(pool_id: str, authorization: str | None = Header(default=None)):
        require_auth_key(authorization)
        pool = cpa_config.get_pool(pool_id)
        if pool is None:
            raise HTTPException(status_code=404, detail={"error": "pool not found"})
        return {"import_job": pool.get("import_job")}


def register_admin_routes(
    router: APIRouter,
    *,
    app_version: str,
    chatgpt_service: ChatGPTService,
    require_auth_key,
) -> None:
    register_model_routes(router)
    register_meta_routes(router, app_version=app_version, require_auth_key=require_auth_key)
    register_account_routes(router, require_auth_key=require_auth_key)
    register_openai_routes(router, chatgpt_service=chatgpt_service, require_auth_key=require_auth_key)
    register_cpa_routes(router, require_auth_key=require_auth_key)
