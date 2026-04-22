from __future__ import annotations

from contextlib import asynccontextmanager
import os
from pathlib import Path
from threading import Event, Thread

from fastapi import APIRouter, FastAPI, File, Form, Header, HTTPException, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field

from services.account_service import account_service
from services.api_public_panel import register_public_panel_routes
from services.chatgpt_service import ChatGPTService
from services.config import (
    IMAGE_CONCURRENT_LIMIT,
    IMAGE_COUNT_LIMIT,
    IMAGE_RETRY_LIMIT,
    config,
    get_image_settings,
    update_image_settings,
)
from services.cpa_service import cpa_config, cpa_import_service, list_remote_files
from services.image_workflow_service import ImageWorkflowService
from services.image_service import ImageGenerationError
from services.public_panel_service import PublicPanelService
from services.streaming import iter_chat_completion_sse, iter_response_sse
from services.utils import parse_image_response_format
from services.version import get_app_version

BASE_DIR = Path(__file__).resolve().parents[1]


def resolve_web_dist_dir() -> Path:
    variant = str(os.getenv("CHATGPT2API_WEB_VARIANT") or "admin").strip().lower()
    return BASE_DIR / "web_dist_studio" if variant == "studio" else BASE_DIR / "web_dist"


WEB_DIST_DIR = resolve_web_dist_dir()
STUDIO_BLOCKED_PREFIXES = ("accounts", "settings", "login", "image")


class ImageGenerationRequest(BaseModel):
    prompt: str = Field(..., min_length=1)
    model: str = "gpt-image-2"
    n: int = Field(default=1, ge=1)
    response_format: str = "url"
    history_disabled: bool = True


class ImageSettingsUpdateRequest(BaseModel):
    default_model: str | None = None
    max_count_per_request: int | None = Field(default=None, ge=1, le=IMAGE_COUNT_LIMIT)
    max_concurrent_jobs: int | None = Field(default=None, ge=1, le=IMAGE_CONCURRENT_LIMIT)
    auto_retry_times: int | None = Field(default=None, ge=0, le=IMAGE_RETRY_LIMIT)


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
    return {
        key: value
        for key, value in pool.items()
        if key != "secret_key"
    }


def sanitize_cpa_pools(pools: list[dict]) -> list[dict]:
    return [sanitized for pool in pools if (sanitized := sanitize_cpa_pool(pool)) is not None]


def serialize_image_settings() -> dict[str, object]:
    settings = get_image_settings()
    return {
        "default_model": settings.default_model,
        "max_count_per_request": settings.max_count_per_request,
        "max_concurrent_jobs": settings.max_concurrent_jobs,
        "auto_retry_times": settings.auto_retry_times,
    }


def validate_image_count(n: int) -> int:
    settings = get_image_settings()
    if n < 1 or n > settings.max_count_per_request:
        raise HTTPException(
            status_code=400,
            detail={"error": f"n must be between 1 and {settings.max_count_per_request}"},
        )
    return n


def extract_bearer_token(authorization: str | None) -> str:
    scheme, _, value = str(authorization or "").partition(" ")
    if scheme.lower() != "bearer" or not value.strip():
        return ""
    return value.strip()


def require_auth_key(authorization: str | None) -> None:
    if extract_bearer_token(authorization) != str(config.auth_key or "").strip():
        raise HTTPException(status_code=401, detail={"error": "authorization is invalid"})


def start_limited_account_watcher(stop_event: Event) -> Thread:
    interval_seconds = config.refresh_account_interval_minute * 60

    def worker() -> None:
        while not stop_event.is_set():
            try:
                limited_tokens = account_service.list_limited_tokens()
                if limited_tokens:
                    print(f"[account-limited-watcher] checking {len(limited_tokens)} limited accounts")
                    account_service.refresh_accounts(limited_tokens)
            except Exception as exc:
                print(f"[account-limited-watcher] fail {exc}")
            stop_event.wait(interval_seconds)

    thread = Thread(target=worker, name="limited-account-watcher", daemon=True)
    thread.start()
    return thread


def resolve_web_asset(requested_path: str) -> Path | None:
    if not WEB_DIST_DIR.exists():
        return None

    clean_path = requested_path.strip("/")
    if not clean_path:
        candidates = [WEB_DIST_DIR / "index.html"]
    else:
        relative_path = Path(clean_path)
        candidates = [
            WEB_DIST_DIR / relative_path,
            WEB_DIST_DIR / relative_path / "index.html",
            WEB_DIST_DIR / f"{clean_path}.html",
        ]

    for candidate in candidates:
        try:
            candidate.relative_to(WEB_DIST_DIR)
        except ValueError:
            continue
        if candidate.is_file():
            return candidate

    return None


def should_block_studio_page(requested_path: str) -> bool:
    if WEB_DIST_DIR.name != "web_dist_studio":
        return False
    clean_path = requested_path.strip("/")
    if not clean_path:
        return False
    return any(clean_path == prefix or clean_path.startswith(f"{prefix}/") for prefix in STUDIO_BLOCKED_PREFIXES)


def create_app() -> FastAPI:
    chatgpt_service = ChatGPTService(account_service)
    public_panel_service = PublicPanelService(config.public_panel_file)
    image_workflow_service = ImageWorkflowService(
        quota_gateway=public_panel_service,
        image_backend=chatgpt_service,
    )
    app_version = get_app_version()

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        stop_event = Event()
        thread = start_limited_account_watcher(stop_event)
        try:
            yield
        finally:
            stop_event.set()
            thread.join(timeout=1)

    app = FastAPI(title="chatgpt2api", version=app_version, lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.mount("/generated-images", StaticFiles(directory=config.generated_images_dir), name="generated-images")
    router = APIRouter()

    @router.get("/v1/models")
    async def list_models():
        return {
            "object": "list",
            "data": [
                build_model_item("gpt-image-1"),
                build_model_item("gpt-image-2"),
            ],
        }

    @router.post("/auth/login")
    async def login(authorization: str | None = Header(default=None)):
        require_auth_key(authorization)
        return {"ok": True, "version": app_version}

    @router.get("/version")
    async def get_version():
        return {"version": app_version}

    @router.get("/api/accounts")
    async def get_accounts(authorization: str | None = Header(default=None)):
        require_auth_key(authorization)
        return {"items": account_service.list_accounts()}

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

        updates = {
            key: value
            for key, value in {
                "type": body.type,
                "status": body.status,
                "quota": body.quota,
            }.items()
            if value is not None
        }
        if not updates:
            raise HTTPException(status_code=400, detail={"error": "no updates provided"})

        account = account_service.update_account(access_token, updates)
        if account is None:
            raise HTTPException(status_code=404, detail={"error": "account not found"})
        return {"item": account, "items": account_service.list_accounts()}

    @router.post("/v1/images/generations")
    async def generate_images(body: ImageGenerationRequest, authorization: str | None = Header(default=None)):
        require_auth_key(authorization)
        validate_image_count(body.n)
        response_format = parse_image_response_format(body.response_format)
        try:
            return await run_in_threadpool(
                image_workflow_service.generate_admin,
                body.prompt,
                body.model,
                body.n,
                response_format,
            )
        except ImageGenerationError as exc:
            raise HTTPException(status_code=502, detail={"error": str(exc)}) from exc

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
        validate_image_count(n)
        normalized_response_format = parse_image_response_format(response_format)

        images: list[tuple[bytes, str, str]] = []
        for upload in image:
            image_data = await upload.read()
            if not image_data:
                raise HTTPException(status_code=400, detail={"error": "image file is empty"})

            file_name = upload.filename or "image.png"
            mime_type = upload.content_type or "image/png"
            images.append((image_data, file_name, mime_type))

        try:
            return await run_in_threadpool(
                image_workflow_service.edit_admin,
                prompt,
                images,
                model,
                n,
                normalized_response_format,
            )
        except ImageGenerationError as exc:
            raise HTTPException(status_code=502, detail={"error": str(exc)}) from exc

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

    # ── CPA multi-pool endpoints ────────────────────────────────────

    @router.get("/api/cpa/pools")
    async def list_cpa_pools(authorization: str | None = Header(default=None)):
        require_auth_key(authorization)
        return {"pools": sanitize_cpa_pools(cpa_config.list_pools())}

    @router.post("/api/cpa/pools")
    async def create_cpa_pool(
            body: CPAPoolCreateRequest,
            authorization: str | None = Header(default=None),
    ):
        require_auth_key(authorization)
        if not body.base_url.strip():
            raise HTTPException(status_code=400, detail={"error": "base_url is required"})
        if not body.secret_key.strip():
            raise HTTPException(status_code=400, detail={"error": "secret_key is required"})
        pool = cpa_config.add_pool(
            name=body.name,
            base_url=body.base_url,
            secret_key=body.secret_key,
        )
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
    async def delete_cpa_pool(
            pool_id: str,
            authorization: str | None = Header(default=None),
    ):
        require_auth_key(authorization)
        if not cpa_config.delete_pool(pool_id):
            raise HTTPException(status_code=404, detail={"error": "pool not found"})
        return {"pools": sanitize_cpa_pools(cpa_config.list_pools())}

    @router.get("/api/cpa/pools/{pool_id}/files")
    async def cpa_pool_files(
            pool_id: str,
            authorization: str | None = Header(default=None),
    ):
        require_auth_key(authorization)
        pool = cpa_config.get_pool(pool_id)
        if pool is None:
            raise HTTPException(status_code=404, detail={"error": "pool not found"})
        files = await run_in_threadpool(list_remote_files, pool)
        return {"pool_id": pool_id, "files": files}

    @router.post("/api/cpa/pools/{pool_id}/import")
    async def cpa_pool_import(
            pool_id: str,
            body: CPAImportRequest,
            authorization: str | None = Header(default=None),
    ):
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

    register_public_panel_routes(
        router,
        public_panel_service=public_panel_service,
        image_workflow_service=image_workflow_service,
        image_request_model=ImageGenerationRequest,
        require_auth_key=require_auth_key,
        validate_image_count=validate_image_count,
    )

    app.include_router(router)

    @app.api_route("/{full_path:path}", methods=["GET", "HEAD"], include_in_schema=False)
    async def serve_web(full_path: str):
        if should_block_studio_page(full_path):
            raise HTTPException(status_code=404, detail="Not Found")
        asset = resolve_web_asset(full_path)
        if asset is not None:
            return FileResponse(asset)

        # Static assets (_next/*) must not fallback to HTML — return 404
        if full_path.strip("/").startswith("_next/"):
            raise HTTPException(status_code=404, detail="Not Found")

        fallback = resolve_web_asset("")
        if fallback is None:
            raise HTTPException(status_code=404, detail="Not Found")
        return FileResponse(fallback)

    return app
