from __future__ import annotations

from fastapi import APIRouter, Body, Cookie, File, Form, Header, HTTPException, UploadFile
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, Field

from services.api_public_auth import SESSION_COOKIE_NAME
from services.image_service import ImageGenerationError

FORBIDDEN_PUBLIC_ERRORS = {
    "public panel is disabled",
    "public panel quota is insufficient",
    "public user balance is insufficient",
    "model price is unavailable",
}


class PublicPanelConfigUpdateRequest(BaseModel):
    enabled: bool
    title: str = ""
    description: str = ""
    mode: str = Field(default="daily")
    daily_limit: int = Field(default=0, ge=0)
    fixed_quota: int = Field(default=0, ge=0)


class PublicPanelQuotaAddRequest(BaseModel):
    amount: int = Field(..., gt=0)


def register_public_panel_routes(
    router: APIRouter,
    *,
    public_panel_service,
    image_workflow_service,
    public_auth_service,
    image_request_model: type[BaseModel],
    require_auth_key,
) -> None:
    @router.get("/api/public-panel/status")
    async def get_public_panel_status():
        return public_panel_service.get_public_status()

    @router.get("/api/public-panel/config")
    async def get_public_panel_config(authorization: str | None = Header(default=None)):
        require_auth_key(authorization)
        return public_panel_service.get_admin_config()

    @router.post("/api/public-panel/config")
    async def update_public_panel_config(
        body: PublicPanelConfigUpdateRequest,
        authorization: str | None = Header(default=None),
    ):
        require_auth_key(authorization)
        return public_panel_service.update_config(
            enabled=body.enabled,
            title=body.title,
            description=body.description,
            mode=body.mode,
            daily_limit=body.daily_limit,
            fixed_quota=body.fixed_quota,
        )

    @router.post("/api/public-panel/quota/add")
    async def add_public_panel_quota(
        body: PublicPanelQuotaAddRequest,
        authorization: str | None = Header(default=None),
    ):
        require_auth_key(authorization)
        try:
            return public_panel_service.add_quota(body.amount)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail={"error": str(exc)}) from exc

    @router.post("/api/public-panel/images/generations")
    async def generate_public_images(
        body: dict[str, object] = Body(...),
        session_token: str | None = Cookie(default=None, alias=SESSION_COOKIE_NAME),
    ):
        parsed = image_request_model.model_validate(body)
        model = _normalize_public_model(parsed.model)
        public_user_id = _resolve_public_user_id(public_auth_service, session_token)
        try:
            return await run_in_threadpool(
                image_workflow_service.generate_public,
                parsed.prompt,
                model,
                parsed.n,
                public_user_id,
            )
        except ImageGenerationError as exc:
            raise HTTPException(status_code=502, detail={"error": str(exc)}) from exc
        except RuntimeError as exc:
            raise _map_public_runtime_error(exc) from exc

    @router.post("/api/public-panel/images/edits")
    async def edit_public_images(
        image: list[UploadFile] = File(...),
        prompt: str = Form(...),
        model: str = Form(default="gpt-image-1"),
        n: int = Form(default=1),
        session_token: str | None = Cookie(default=None, alias=SESSION_COOKIE_NAME),
    ):
        if n < 1 or n > 4:
            raise HTTPException(status_code=400, detail={"error": "n must be between 1 and 4"})

        images: list[tuple[bytes, str, str]] = []
        for upload in image:
            image_data = await upload.read()
            if not image_data:
                raise HTTPException(status_code=400, detail={"error": "image file is empty"})
            images.append((image_data, upload.filename or "image.png", upload.content_type or "image/png"))

        normalized_model = _normalize_public_model(model)
        public_user_id = _resolve_public_user_id(public_auth_service, session_token)
        try:
            return await run_in_threadpool(
                image_workflow_service.edit_public,
                prompt,
                images,
                normalized_model,
                n,
                public_user_id,
            )
        except ImageGenerationError as exc:
            raise HTTPException(status_code=502, detail={"error": str(exc)}) from exc
        except RuntimeError as exc:
            raise _map_public_runtime_error(exc) from exc


def _resolve_public_user_id(public_auth_service, session_token: str | None) -> str | None:
    if not session_token:
        return None
    user = public_auth_service.get_user_by_session_token(session_token)
    if user is None:
        raise HTTPException(status_code=401, detail={"error": "login required"})
    return user["id"]


def _map_public_runtime_error(error: RuntimeError) -> HTTPException:
    message = str(error)
    if message in FORBIDDEN_PUBLIC_ERRORS:
        return HTTPException(status_code=403, detail={"error": message})
    return HTTPException(status_code=500, detail={"error": message})


def _normalize_public_model(value: object) -> str:
    model = str(value or "").strip()
    if not model or model == "gpt-4o":
        return "gpt-image-1"
    return model
