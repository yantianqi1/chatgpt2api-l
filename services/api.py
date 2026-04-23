from __future__ import annotations

from contextlib import asynccontextmanager
import os
from pathlib import Path
from threading import Event, Thread

from fastapi import APIRouter, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from services.account_service import account_service
from services.api_admin import ImageGenerationRequest, register_admin_routes
from services.api_comic import register_comic_routes
from services.api_public_panel import register_public_panel_routes
from services.chatgpt_service import ChatGPTService
from services.comic.runner import ComicTaskRunner
from services.comic.store import ComicProjectStore
from services.comic.tasks import ComicTaskService
from services.comic.worker import ComicWorker
from services.comic.workflow import ComicWorkflowService
from services.config import config
from services.image_workflow_service import ImageWorkflowService
from services.public_panel_service import PublicPanelService
from services.version import get_app_version

BASE_DIR = Path(__file__).resolve().parents[1]


def resolve_web_dist_dir() -> Path:
    variant = str(os.getenv("CHATGPT2API_WEB_VARIANT") or "admin").strip().lower()
    return BASE_DIR / "web_dist_studio" if variant == "studio" else BASE_DIR / "web_dist"


WEB_DIST_DIR = resolve_web_dist_dir()
STUDIO_BLOCKED_PREFIXES = ("accounts", "settings", "login", "image")


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
    image_workflow_service = ImageWorkflowService(quota_gateway=public_panel_service, image_backend=chatgpt_service)
    comic_store = ComicProjectStore(config.comic_projects_dir)
    comic_task_service = ComicTaskService(comic_store)
    comic_workflow_service = ComicWorkflowService(chatgpt_service)
    comic_task_runner = ComicTaskRunner(
        store=comic_store,
        task_service=comic_task_service,
        workflow_service=comic_workflow_service,
    )
    comic_worker = ComicWorker(task_service=comic_task_service, runner=comic_task_runner.run_task)
    app_version = get_app_version()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        stop_event = Event()
        thread = start_limited_account_watcher(stop_event)
        comic_worker.start()
        try:
            app.state.comic_store = comic_store
            app.state.comic_task_service = comic_task_service
            app.state.comic_task_runner = comic_task_runner
            app.state.comic_worker = comic_worker
            yield
        finally:
            stop_event.set()
            comic_worker.stop()
            thread.join(timeout=1)

    app = FastAPI(title="chatgpt2api", version=app_version, lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    router = APIRouter()
    register_admin_routes(router, app_version=app_version, chatgpt_service=chatgpt_service, require_auth_key=require_auth_key)
    register_public_panel_routes(
        router,
        public_panel_service=public_panel_service,
        image_workflow_service=image_workflow_service,
        image_request_model=ImageGenerationRequest,
        require_auth_key=require_auth_key,
    )
    register_comic_routes(router)

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
