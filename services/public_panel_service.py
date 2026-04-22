from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from uuid import uuid4
from zoneinfo import ZoneInfo

MODE_DAILY = "daily"
MODE_FIXED = "fixed"
SHANGHAI_TZ = ZoneInfo("Asia/Shanghai")


@dataclass(frozen=True)
class PublicPanelConfig:
    enabled: bool
    title: str
    description: str
    mode: str
    daily_limit: int
    daily_used: int
    daily_reset_date: str
    fixed_quota: int
    updated_at: str


@dataclass(frozen=True)
class QuotaReservation:
    count: int
    mode: str
    day_key: str


class PublicPanelService:
    def __init__(self, store_file: Path):
        self.store_file = store_file
        self._lock = Lock()
        self._reservations: dict[str, QuotaReservation] = {}
        self._config = self._load_config()

    def get_public_status(self) -> dict[str, object]:
        with self._lock:
            self._reload_from_file_locked()
            self._refresh_daily_quota_locked()
            return self._serialize_status_locked()

    def get_admin_config(self) -> dict[str, object]:
        return self.get_public_status()

    def update_config(
        self,
        *,
        enabled: bool,
        title: str,
        description: str,
        mode: str,
        daily_limit: int,
        fixed_quota: int,
    ) -> dict[str, object]:
        normalized_mode = self._normalize_mode(mode)
        next_config = PublicPanelConfig(
            enabled=bool(enabled),
            title=str(title or "").strip(),
            description=str(description or "").strip(),
            mode=normalized_mode,
            daily_limit=max(0, int(daily_limit)),
            daily_used=max(0, int(self._config.daily_used if normalized_mode == self._config.mode else 0)),
            daily_reset_date=self._today_key(),
            fixed_quota=max(0, int(fixed_quota)),
            updated_at=self._build_timestamp(),
        )
        with self._lock:
            self._reload_from_file_locked()
            self._refresh_daily_quota_locked()
            if normalized_mode == MODE_DAILY:
                next_config = PublicPanelConfig(
                    enabled=next_config.enabled,
                    title=next_config.title,
                    description=next_config.description,
                    mode=next_config.mode,
                    daily_limit=next_config.daily_limit,
                    daily_used=max(0, min(self._config.daily_used, next_config.daily_limit))
                    if self._config.mode == MODE_DAILY
                    else 0,
                    daily_reset_date=self._today_key(),
                    fixed_quota=next_config.fixed_quota,
                    updated_at=next_config.updated_at,
                )
            self._config = next_config
            self._save_config(next_config)
            return self._serialize_status_locked()

    def add_quota(self, amount: int) -> dict[str, object]:
        increment = int(amount)
        if increment <= 0:
            raise ValueError("amount must be greater than 0")
        with self._lock:
            self._reload_from_file_locked()
            self._refresh_daily_quota_locked()
            if self._config.mode != MODE_FIXED:
                raise ValueError("fixed mode is required to add quota")
            next_config = PublicPanelConfig(
                enabled=self._config.enabled,
                title=self._config.title,
                description=self._config.description,
                mode=self._config.mode,
                daily_limit=self._config.daily_limit,
                daily_used=self._config.daily_used,
                daily_reset_date=self._config.daily_reset_date,
                fixed_quota=self._config.fixed_quota + increment,
                updated_at=self._build_timestamp(),
            )
            self._config = next_config
            self._save_config(next_config)
            return self._serialize_status_locked()

    def reserve_quota(self, count: int) -> str:
        requested = int(count)
        if requested <= 0:
            raise ValueError("count must be greater than 0")
        with self._lock:
            self._reload_from_file_locked()
            self._refresh_daily_quota_locked()
            if not self._config.enabled:
                raise RuntimeError("public panel is disabled")
            if self._available_quota_locked() < requested:
                raise RuntimeError("public panel quota is insufficient")
            token = uuid4().hex
            self._reservations[token] = QuotaReservation(
                count=requested,
                mode=self._config.mode,
                day_key=self._config.daily_reset_date,
            )
            return token

    def commit_reservation(self, token: str) -> dict[str, object]:
        with self._lock:
            self._reload_from_file_locked()
            self._refresh_daily_quota_locked()
            reservation = self._pop_reservation_locked(token)
            next_config = self._config
            if reservation.mode == MODE_FIXED:
                next_config = PublicPanelConfig(
                    enabled=self._config.enabled,
                    title=self._config.title,
                    description=self._config.description,
                    mode=self._config.mode,
                    daily_limit=self._config.daily_limit,
                    daily_used=self._config.daily_used,
                    daily_reset_date=self._config.daily_reset_date,
                    fixed_quota=max(0, self._config.fixed_quota - reservation.count),
                    updated_at=self._build_timestamp(),
                )
            if reservation.mode == MODE_DAILY:
                next_used = self._config.daily_used
                if reservation.day_key == self._config.daily_reset_date:
                    next_used = min(self._config.daily_limit, self._config.daily_used + reservation.count)
                next_config = PublicPanelConfig(
                    enabled=self._config.enabled,
                    title=self._config.title,
                    description=self._config.description,
                    mode=self._config.mode,
                    daily_limit=self._config.daily_limit,
                    daily_used=next_used,
                    daily_reset_date=self._config.daily_reset_date,
                    fixed_quota=self._config.fixed_quota,
                    updated_at=self._build_timestamp(),
                )
            self._config = next_config
            self._save_config(next_config)
            return self._serialize_status_locked()

    def release_reservation(self, token: str) -> None:
        with self._lock:
            self._pop_reservation_locked(token)

    def _load_config(self) -> PublicPanelConfig:
        if not self.store_file.exists():
            return self._default_config()
        payload = json.loads(self.store_file.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("public_panel.json must be a JSON object")
        return self._normalize_config(payload)

    def _reload_from_file_locked(self) -> None:
        if not self.store_file.exists():
            self._config = self._default_config()
            return
        self._config = self._load_config()

    def _save_config(self, config: PublicPanelConfig) -> None:
        self.store_file.parent.mkdir(parents=True, exist_ok=True)
        content = json.dumps(asdict(config), ensure_ascii=False, indent=2) + "\n"
        self.store_file.write_text(content, encoding="utf-8")

    def _normalize_config(self, payload: dict[str, object]) -> PublicPanelConfig:
        return PublicPanelConfig(
            enabled=bool(payload.get("enabled", False)),
            title=str(payload.get("title") or "").strip(),
            description=str(payload.get("description") or "").strip(),
            mode=self._normalize_mode(payload.get("mode")),
            daily_limit=max(0, int(payload.get("daily_limit") or 0)),
            daily_used=max(0, int(payload.get("daily_used") or 0)),
            daily_reset_date=str(payload.get("daily_reset_date") or "").strip() or self._today_key(),
            fixed_quota=max(0, int(payload.get("fixed_quota") or payload.get("quota") or 0)),
            updated_at=str(payload.get("updated_at") or "").strip() or self._build_timestamp(),
        )

    def _refresh_daily_quota_locked(self) -> None:
        if self._config.daily_reset_date == self._today_key():
            return
        self._config = PublicPanelConfig(
            enabled=self._config.enabled,
            title=self._config.title,
            description=self._config.description,
            mode=self._config.mode,
            daily_limit=self._config.daily_limit,
            daily_used=0,
            daily_reset_date=self._today_key(),
            fixed_quota=self._config.fixed_quota,
            updated_at=self._build_timestamp(),
        )
        self._save_config(self._config)

    def _serialize_status_locked(self) -> dict[str, object]:
        available_quota = self._available_quota_locked()
        disabled_reason = None
        if not self._config.enabled:
            disabled_reason = "disabled"
        if self._config.enabled and available_quota <= 0:
            disabled_reason = "quota_exhausted"
        payload = asdict(self._config)
        payload["available_quota"] = max(0, available_quota)
        payload["quota"] = max(0, available_quota)
        payload["disabled_reason"] = disabled_reason
        return payload

    def _available_quota_locked(self) -> int:
        if self._config.mode == MODE_FIXED:
            reserved = sum(
                reservation.count
                for reservation in self._reservations.values()
                if reservation.mode == MODE_FIXED
            )
            return self._config.fixed_quota - reserved
        reserved = sum(
            reservation.count
            for reservation in self._reservations.values()
            if reservation.mode == MODE_DAILY and reservation.day_key == self._config.daily_reset_date
        )
        return self._config.daily_limit - self._config.daily_used - reserved

    def _pop_reservation_locked(self, token: str) -> QuotaReservation:
        reservation_key = str(token or "").strip()
        reservation = self._reservations.pop(reservation_key, None)
        if reservation is None:
            raise KeyError("reservation not found")
        return reservation

    def _default_config(self) -> PublicPanelConfig:
        return PublicPanelConfig(
            enabled=False,
            title="",
            description="",
            mode=MODE_DAILY,
            daily_limit=0,
            daily_used=0,
            daily_reset_date=self._today_key(),
            fixed_quota=0,
            updated_at=self._build_timestamp(),
        )

    @staticmethod
    def _normalize_mode(value: object) -> str:
        mode = str(value or MODE_DAILY).strip().lower()
        if mode not in {MODE_DAILY, MODE_FIXED}:
            raise ValueError("mode must be 'daily' or 'fixed'")
        return mode

    @staticmethod
    def _build_timestamp() -> str:
        return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    @staticmethod
    def _now_shanghai() -> datetime:
        return datetime.now(SHANGHAI_TZ)

    @classmethod
    def _today_key(cls) -> str:
        return cls._now_shanghai().date().isoformat()
