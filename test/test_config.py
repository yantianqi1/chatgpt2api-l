import json
import sys
import tempfile
import types
import unittest
from pathlib import Path

if "curl_cffi.requests" not in sys.modules:
    curl_cffi_module = types.ModuleType("curl_cffi")
    requests_module = types.ModuleType("curl_cffi.requests")
    requests_module.Session = object
    curl_cffi_module.requests = requests_module
    sys.modules["curl_cffi"] = curl_cffi_module
    sys.modules["curl_cffi.requests"] = requests_module

from services.image_service import (
    LONG_REQUEST_TIMEOUT_SECONDS,
    MEDIUM_REQUEST_TIMEOUT_SECONDS,
    SHORT_REQUEST_TIMEOUT_SECONDS,
)
from services.text_service import TEXT_REQUEST_TIMEOUT_SECONDS

IMAGE_TIMEOUT_SECONDS = 300


ROOT_DIR = Path(__file__).resolve().parents[1]
ROOT_CONFIG_FILE = ROOT_DIR / "config.json"


class ConfigLoadingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._created_root_config = False
        if not ROOT_CONFIG_FILE.exists():
            ROOT_CONFIG_FILE.write_text(json.dumps({"auth-key": "test-auth"}), encoding="utf-8")
            cls._created_root_config = True

        from services import config as config_module

        cls.config_module = config_module

    @classmethod
    def tearDownClass(cls) -> None:
        if cls._created_root_config and ROOT_CONFIG_FILE.exists():
            ROOT_CONFIG_FILE.unlink()

    def test_load_settings_ignores_directory_config_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            base_dir = Path(tmp_dir)
            data_dir = base_dir / "data"
            config_dir = base_dir / "config.json"
            os_auth_key = "env-auth"

            config_dir.mkdir()

            module = self.config_module
            old_base_dir = module.BASE_DIR
            old_data_dir = module.DATA_DIR
            old_config_file = module.CONFIG_FILE
            old_env_auth_key = module.os.environ.get("CHATGPT2API_AUTH_KEY")
            try:
                module.BASE_DIR = base_dir
                module.DATA_DIR = data_dir
                module.CONFIG_FILE = config_dir
                module.os.environ["CHATGPT2API_AUTH_KEY"] = os_auth_key

                settings = module._load_settings()

                self.assertEqual(settings.auth_key, os_auth_key)
                self.assertEqual(settings.refresh_account_interval_minute, 60)
            finally:
                module.BASE_DIR = old_base_dir
                module.DATA_DIR = old_data_dir
                module.CONFIG_FILE = old_config_file
                if old_env_auth_key is None:
                    module.os.environ.pop("CHATGPT2API_AUTH_KEY", None)
                else:
                    module.os.environ["CHATGPT2API_AUTH_KEY"] = old_env_auth_key

    def test_image_settings_use_defaults_and_persist_updates(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            base_dir = Path(tmp_dir)
            data_dir = base_dir / "data"
            config_file = base_dir / "config.json"
            config_file.write_text(json.dumps({"auth-key": "file-auth"}), encoding="utf-8")

            module = self.config_module
            old_base_dir = module.BASE_DIR
            old_data_dir = module.DATA_DIR
            old_config_file = module.CONFIG_FILE
            try:
                module.BASE_DIR = base_dir
                module.DATA_DIR = data_dir
                module.CONFIG_FILE = config_file

                settings = module.get_image_settings()
                self.assertEqual(settings.default_model, "gpt-image-2")
                self.assertEqual(settings.max_count_per_request, 4)
                self.assertEqual(settings.auto_retry_times, 1)
                self.assertEqual(SHORT_REQUEST_TIMEOUT_SECONDS, IMAGE_TIMEOUT_SECONDS)
                self.assertEqual(MEDIUM_REQUEST_TIMEOUT_SECONDS, IMAGE_TIMEOUT_SECONDS)
                self.assertEqual(LONG_REQUEST_TIMEOUT_SECONDS, IMAGE_TIMEOUT_SECONDS)
                self.assertEqual(TEXT_REQUEST_TIMEOUT_SECONDS, IMAGE_TIMEOUT_SECONDS)
                self.assertEqual(module.IMAGE_REQUEST_TIMEOUT_SECONDS, IMAGE_TIMEOUT_SECONDS)
                self.assertEqual(module.IMAGE_TIMEOUT_LIMIT, IMAGE_TIMEOUT_SECONDS)
                self.assertEqual(settings.request_timeout_seconds, IMAGE_TIMEOUT_SECONDS)

                updated = module.update_image_settings(
                    {
                        "default_model": "gpt-image-1",
                        "max_count_per_request": 6,
                        "auto_retry_times": 3,
                        "request_timeout_seconds": 45,
                    }
                )
                self.assertEqual(updated.default_model, "gpt-image-1")
                self.assertEqual(updated.max_count_per_request, 6)
                self.assertEqual(updated.auto_retry_times, 3)
                self.assertEqual(updated.request_timeout_seconds, 45)

                persisted = json.loads(config_file.read_text(encoding="utf-8"))
                self.assertEqual(persisted["image_default_model"], "gpt-image-1")
                self.assertEqual(persisted["image_max_count_per_request"], 6)
                self.assertEqual(persisted["image_auto_retry_times"], 3)
                self.assertEqual(persisted["image_request_timeout_seconds"], 45)
            finally:
                module.BASE_DIR = old_base_dir
                module.DATA_DIR = old_data_dir
                module.CONFIG_FILE = old_config_file

    def test_load_settings_reads_public_base_url_from_dotenv(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            base_dir = Path(tmp_dir)
            data_dir = base_dir / "data"
            config_file = base_dir / "config.json"
            env_file = base_dir / ".env"
            env_file.write_text(
                "CHATGPT2API_AUTH_KEY=dotenv-auth\nCHATGPT2API_PUBLIC_BASE_URL=https://img.example.com\n",
                encoding="utf-8",
            )

            module = self.config_module
            old_base_dir = module.BASE_DIR
            old_data_dir = module.DATA_DIR
            old_config_file = module.CONFIG_FILE
            old_env_auth_key = module.os.environ.pop("CHATGPT2API_AUTH_KEY", None)
            old_env_public_base_url = module.os.environ.pop("CHATGPT2API_PUBLIC_BASE_URL", None)
            try:
                module.BASE_DIR = base_dir
                module.DATA_DIR = data_dir
                module.CONFIG_FILE = config_file

                settings = module._load_settings()

                self.assertEqual(settings.auth_key, "dotenv-auth")
                self.assertEqual(settings.public_base_url, "https://img.example.com")
            finally:
                module.BASE_DIR = old_base_dir
                module.DATA_DIR = old_data_dir
                module.CONFIG_FILE = old_config_file
                if old_env_auth_key is not None:
                    module.os.environ["CHATGPT2API_AUTH_KEY"] = old_env_auth_key
                if old_env_public_base_url is not None:
                    module.os.environ["CHATGPT2API_PUBLIC_BASE_URL"] = old_env_public_base_url


if __name__ == "__main__":
    unittest.main()
