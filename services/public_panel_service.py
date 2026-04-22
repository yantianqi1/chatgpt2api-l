from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, UTC
from pathlib import Path
from threading import Lock
from uuid import uuid4


@dataclass(frozen=True)
class PublicPanelConfig:
    enabled: bool
    quota: int
    title: str
    description: str
    updated_at: str


class PublicPanelService:
    def __init__(self, store_file: Path):
        self.store_file = store_file
        self._lock = Lock()
        self._reservations: dict[str, int] = {}
        self._config = self._load_config()

    def get_public_status(self) -> dict[str, object]:
        with self._lock:
            return self._serialize_config(self._config)

    def get_admin_config(self) -> dict[str, object]:
        return self.get_public_status()

    def update_config(self, *, enabled: bool, quota: int, title: str, description: str) -> dict[str, object]:
        normalized = PublicPanelConfig(
            enabled=bool(enabled),
            quota=max(0, int(quota)),
            title=str(title or "").strip(),
            description=str(description or "").strip(),
            updated_at=self._build_timestamp(),
        )
        with self._lock:
            self._config = normalized
            self._save_config(normalized)
            return self._serialize_config(normalized)

    def add_quota(self, amount: int) -> dict[str, object]:
        increment = int(amount)
        if increment <= 0:
            raise ValueError("amount must be greater than 0")
        with self._lock:
            next_config = PublicPanelConfig(
                enabled=self._config.enabled,
                quota=self._config.quota + increment,
                title=self._config.title,
                description=self._config.description,
                updated_at=self._build_timestamp(),
            )
            self._config = next_config
            self._save_config(next_config)
            return self._serialize_config(next_config)

    def reserve_quota(self, count: int) -> str:
        requested = int(count)
        if requested <= 0:
            raise ValueError("count must be greater than 0")
        with self._lock:
            if not self._config.enabled:
                raise RuntimeError("public panel is disabled")
            if self._available_quota() < requested:
                raise RuntimeError("public panel quota is insufficient")
            token = uuid4().hex
            self._reservations[token] = requested
            return token

    def commit_reservation(self, token: str) -> dict[str, object]:
        with self._lock:
            reserved = self._pop_reservation(token)
            next_quota = self._config.quota - reserved
            next_config = PublicPanelConfig(
                enabled=self._config.enabled,
                quota=max(0, next_quota),
                title=self._config.title,
                description=self._config.description,
                updated_at=self._build_timestamp(),
            )
            self._config = next_config
            self._save_config(next_config)
            return self._serialize_config(next_config)

    def release_reservation(self, token: str) -> None:
        with self._lock:
            self._pop_reservation(token)

    def _load_config(self) -> PublicPanelConfig:
        if not self.store_file.exists():
            return self._default_config()
        payload = json.loads(self.store_file.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("public_panel.json must be a JSON object")
        return self._normalize_config(payload)

    def _save_config(self, config: PublicPanelConfig) -> None:
        self.store_file.parent.mkdir(parents=True, exist_ok=True)
        content = json.dumps(asdict(config), ensure_ascii=False, indent=2) + "\n"
        self.store_file.write_text(content, encoding="utf-8")

    def _normalize_config(self, payload: dict[str, object]) -> PublicPanelConfig:
        quota = int(payload.get("quota") or 0)
        return PublicPanelConfig(
            enabled=bool(payload.get("enabled", False)),
            quota=max(0, quota),
            title=str(payload.get("title") or "").strip(),
            description=str(payload.get("description") or "").strip(),
            updated_at=str(payload.get("updated_at") or "").strip() or self._build_timestamp(),
        )

    def _available_quota(self) -> int:
        reserved = sum(self._reservations.values())
        return self._config.quota - reserved

    def _pop_reservation(self, token: str) -> int:
        reservation_key = str(token or "").strip()
        reserved = self._reservations.pop(reservation_key, None)
        if reserved is None:
            raise KeyError("reservation not found")
        return reserved

    @staticmethod
    def _default_config() -> PublicPanelConfig:
        return PublicPanelConfig(
            enabled=False,
            quota=0,
            title="",
            description="",
            updated_at=PublicPanelService._build_timestamp(),
        )

    @staticmethod
    def _serialize_config(config: PublicPanelConfig) -> dict[str, object]:
        return asdict(config)

    @staticmethod
    def _build_timestamp() -> str:
        return datetime.now(UTC).isoformat().replace("+00:00", "Z")
