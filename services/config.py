from __future__ import annotations
import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from threading import Lock
from typing import cast

BASE_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = BASE_DIR / "data"
CONFIG_FILE = BASE_DIR / "config.json"

IMAGE_DEFAULT_MODEL = "gpt-image-2"
IMAGE_MAX_COUNT_PER_REQUEST = 4
IMAGE_AUTO_RETRY_TIMES = 1
IMAGE_REQUEST_TIMEOUT_SECONDS = 180
IMAGE_COUNT_LIMIT = 10
IMAGE_RETRY_LIMIT = 3
IMAGE_TIMEOUT_LIMIT = 600
IMAGE_MODEL_VALUES = {"gpt-image-1", "gpt-image-2"}
_CONFIG_LOCK = Lock()


@dataclass(frozen=True)
class AppSettings:
    auth_key: str
    host: str
    port: int
    accounts_file: Path
    public_billing_file: Path
    public_panel_file: Path
    public_base_url: str
    generated_images_dir: Path
    comic_projects_dir: Path
    refresh_account_interval_minute: int


@dataclass(frozen=True)
class ImageSettings:
    default_model: str
    max_count_per_request: int
    auto_retry_times: int
    request_timeout_seconds: int


def _load_dotenv() -> None:
    env_file = BASE_DIR / ".env"
    if not env_file.exists() or env_file.is_dir():
        return

    for raw_line in env_file.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        key, separator, value = line.partition("=")
        if not separator:
            continue
        env_key = key.strip()
        if not env_key or env_key in os.environ:
            continue
        normalized = value.strip().strip("'").strip('"')
        os.environ[env_key] = normalized


def _readable_json_file(path: Path, *, name: str) -> Path | None:
    if not path.exists():
        return None
    if path.is_dir():
        print(
            f"Warning: {name} at '{path}' is a directory, ignoring it and falling back to other configuration sources.",
            file=sys.stderr,
        )
        return None
    return path


def _load_json_object(path: Path, *, name: str) -> dict[str, object]:
    text = path.read_text(encoding="utf-8").strip()
    if not text:
        return {}
    loaded = json.loads(text)
    if not isinstance(loaded, dict):
        raise ValueError(f"{name} must be a JSON object")
    return loaded


def _read_raw_config() -> dict[str, object]:
    config_file = _readable_json_file(CONFIG_FILE, name="config.json")
    if config_file is None:
        return {}
    return _load_json_object(config_file, name="config.json")


def _write_raw_config(raw_config: dict[str, object]) -> None:
    CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
    CONFIG_FILE.write_text(json.dumps(raw_config, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _normalize_image_model(value: object) -> str:
    model = str(value or "").strip()
    return model if model in IMAGE_MODEL_VALUES else IMAGE_DEFAULT_MODEL


def _normalize_int(value: object, *, default: int, minimum: int, maximum: int) -> int:
    try:
        normalized = int(value)
    except (TypeError, ValueError):
        normalized = default
    return max(minimum, min(maximum, normalized))


def _normalize_public_base_url(value: object, *, port: int) -> str:
    base_url = str(value or "").strip().rstrip("/")
    if base_url:
        return base_url

    fallback = f"http://127.0.0.1:{port}"
    print(
        "Warning: CHATGPT2API_PUBLIC_BASE_URL is not set, "
        f"falling back to {fallback}. Configure it in .env for server deployments.",
        file=sys.stderr,
    )
    return fallback


def get_image_settings() -> ImageSettings:
    raw_config = _read_raw_config()
    return ImageSettings(
        default_model=_normalize_image_model(raw_config.get("image_default_model")),
        max_count_per_request=_normalize_int(
            raw_config.get("image_max_count_per_request"),
            default=IMAGE_MAX_COUNT_PER_REQUEST,
            minimum=1,
            maximum=IMAGE_COUNT_LIMIT,
        ),
        auto_retry_times=_normalize_int(
            raw_config.get("image_auto_retry_times"),
            default=IMAGE_AUTO_RETRY_TIMES,
            minimum=0,
            maximum=IMAGE_RETRY_LIMIT,
        ),
        request_timeout_seconds=_normalize_int(
            raw_config.get("image_request_timeout_seconds"),
            default=IMAGE_REQUEST_TIMEOUT_SECONDS,
            minimum=0,
            maximum=IMAGE_TIMEOUT_LIMIT,
        ),
    )


def update_image_settings(updates: dict[str, object]) -> ImageSettings:
    with _CONFIG_LOCK:
        raw_config = _read_raw_config()
        if "default_model" in updates:
            raw_config["image_default_model"] = _normalize_image_model(updates.get("default_model"))
        if "max_count_per_request" in updates:
            raw_config["image_max_count_per_request"] = _normalize_int(
                updates.get("max_count_per_request"),
                default=IMAGE_MAX_COUNT_PER_REQUEST,
                minimum=1,
                maximum=IMAGE_COUNT_LIMIT,
            )
        if "auto_retry_times" in updates:
            raw_config["image_auto_retry_times"] = _normalize_int(
                updates.get("auto_retry_times"),
                default=IMAGE_AUTO_RETRY_TIMES,
                minimum=0,
                maximum=IMAGE_RETRY_LIMIT,
            )
        if "request_timeout_seconds" in updates:
            raw_config["image_request_timeout_seconds"] = _normalize_int(
                updates.get("request_timeout_seconds"),
                default=IMAGE_REQUEST_TIMEOUT_SECONDS,
                minimum=0,
                maximum=IMAGE_TIMEOUT_LIMIT,
            )
        raw_config.pop("image_max_concurrent_jobs", None)
        _write_raw_config(raw_config)
    return get_image_settings()


def _load_settings() -> AppSettings:
    _load_dotenv()
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    generated_images_dir = DATA_DIR / "generated-images"
    generated_images_dir.mkdir(parents=True, exist_ok=True)

    # 优先使用环境变量，文件配置仅作为本地/自托管回退
    raw_config = _read_raw_config()
    port = 8000

    auth_key = str(
        os.getenv("CHATGPT2API_AUTH_KEY")
        or raw_config.get("auth-key")
        or ""
    ).strip()

    if not auth_key:
        raise ValueError(
            "❌ auth-key 未设置！\n"
            "请按以下任意一种方式解决：\n"
            "1. 在 Render 的 Environment 变量中添加：\n"
            "   CHATGPT2API_AUTH_KEY = your_real_auth_key\n"
            "2. 或者在 config.json 中填写：\n"
            '   "auth-key": "your_real_auth_key"'
        )

    refresh_account_interval_minute = cast(
        int, raw_config.get("refresh_account_interval_minute", 60)
    )
    public_base_url = _normalize_public_base_url(
        os.getenv("CHATGPT2API_PUBLIC_BASE_URL")
        or raw_config.get("public-base-url"),
        port=port,
    )

    return AppSettings(
        auth_key=auth_key,
        host="0.0.0.0",
        port=port,
        accounts_file=DATA_DIR / "accounts.json",
        public_billing_file=DATA_DIR / "public_billing.db",
        public_panel_file=DATA_DIR / "public_panel.json",
        public_base_url=public_base_url,
        generated_images_dir=generated_images_dir,
        comic_projects_dir=DATA_DIR / "comic-projects",
        refresh_account_interval_minute=refresh_account_interval_minute,
    )


config = _load_settings()
