from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

from services.comic.models import ComicTask
from services.comic.store import ComicProjectStore

STATUS_QUEUED = "queued"
STATUS_RUNNING = "running"
STATUS_COMPLETED = "completed"
STATUS_COMPLETED_WITH_ERRORS = "completed_with_errors"
STATUS_FAILED = "failed"
TASK_STATUSES = {
    STATUS_QUEUED,
    STATUS_RUNNING,
    STATUS_COMPLETED,
    STATUS_COMPLETED_WITH_ERRORS,
    STATUS_FAILED,
}
MAX_PROGRESS = 100
MIN_PROGRESS = 0
STALE_TASK_ERROR = "task became stale while worker was offline"
_MISSING = object()


def _normalize_identifier(value: str, *, name: str) -> str:
    identifier = str(value or "").strip()
    if not identifier or Path(identifier).name != identifier:
        raise ValueError(f"{name} is invalid")
    return identifier


def _normalize_json_object(value: object, *, name: str) -> dict[str, object]:
    if isinstance(value, dict):
        return dict(value)
    raise ValueError(f"{name} must be a JSON object")


class ComicTaskService:
    def __init__(
        self,
        store: ComicProjectStore,
        *,
        now_provider: Callable[[], datetime] | None = None,
    ):
        self.store = store
        self.now_provider = now_provider or (lambda: datetime.now(timezone.utc))

    def create_task(
        self,
        *,
        project_id: str,
        kind: str,
        target_id: str,
        input_payload: dict[str, object],
    ) -> ComicTask:
        timestamp = self._timestamp()
        task = ComicTask(
            id=uuid4().hex,
            project_id=_normalize_identifier(project_id, name="project_id"),
            kind=str(kind or "").strip(),
            status=STATUS_QUEUED,
            target_id=_normalize_identifier(target_id, name="target_id"),
            input_payload=_normalize_json_object(input_payload, name="input_payload"),
            result_payload=None,
            error=None,
            created_at=timestamp,
            updated_at=timestamp,
            progress=MIN_PROGRESS,
        )
        self.store.save_task(task.project_id, task)
        return task

    def list_tasks(self, *, project_id: str | None = None) -> list[ComicTask]:
        paths = self._task_paths(project_id=project_id)
        tasks = [self._load_task(path) for path in paths]
        return sorted(tasks, key=lambda task: (task.created_at, task.id))

    def get_task(self, task_id: str) -> ComicTask:
        task_path = self._find_task_path(task_id)
        return self._load_task(task_path)

    def update_task(
        self,
        task_id: str,
        *,
        status: str,
        result_payload: dict[str, object] | None | object = _MISSING,
        error: str | None | object = _MISSING,
        progress: int | object = _MISSING,
    ) -> ComicTask:
        current = self.get_task(task_id)
        next_status = self._normalize_status(status)
        next_result = current.result_payload if result_payload is _MISSING else self._optional_json_object(result_payload)
        next_error = current.error if error is _MISSING else self._optional_error(error)
        next_progress = current.progress if progress is _MISSING else self._normalize_progress(progress)
        updated = replace(
            current,
            status=next_status,
            result_payload=next_result,
            error=next_error,
            updated_at=self._timestamp(),
            progress=next_progress,
        )
        self.store.save_task(updated.project_id, updated)
        return updated

    def retry_task(self, task_id: str) -> ComicTask:
        current = self.get_task(task_id)
        return self.create_task(
            project_id=current.project_id,
            kind=current.kind,
            target_id=current.target_id,
            input_payload=current.input_payload,
        )

    def recover_stale_tasks(self, *, stale_after_seconds: int) -> list[ComicTask]:
        cutoff = self._now() - timedelta(seconds=int(stale_after_seconds))
        recovered = []
        for task in self.list_tasks():
            if task.status != STATUS_RUNNING:
                continue
            if self._parse_timestamp(task.updated_at) >= cutoff:
                continue
            recovered.append(
                self.update_task(
                    task.id,
                    status=STATUS_FAILED,
                    error=STALE_TASK_ERROR,
                    progress=task.progress,
                )
            )
        return recovered

    def _task_paths(self, *, project_id: str | None = None) -> list[Path]:
        if project_id is None:
            return sorted(self.store.root_dir.glob("*/tasks/*.json"))
        project_key = _normalize_identifier(project_id, name="project_id")
        return sorted((self.store.root_dir / project_key / "tasks").glob("*.json"))

    def _find_task_path(self, task_id: str) -> Path:
        task_key = _normalize_identifier(task_id, name="task_id")
        for path in self._task_paths():
            if path.stem == task_key:
                return path
        raise FileNotFoundError(f"comic task not found: {task_key}")

    def _load_task(self, path: Path) -> ComicTask:
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError(f"{path.name} must be a JSON object")
        return ComicTask.from_dict(dict(payload))

    def _normalize_status(self, status: str) -> str:
        normalized_status = str(status or "").strip()
        if normalized_status not in TASK_STATUSES:
            raise ValueError(f"status is invalid: {normalized_status}")
        return normalized_status

    def _normalize_progress(self, value: object) -> int:
        progress = int(value)
        return max(MIN_PROGRESS, min(MAX_PROGRESS, progress))

    def _optional_json_object(self, value: object) -> dict[str, object] | None:
        if value is None:
            return None
        return _normalize_json_object(value, name="result_payload")

    def _optional_error(self, value: object) -> str | None:
        if value is None:
            return None
        return str(value).strip() or None

    def _timestamp(self) -> str:
        return self._now().isoformat().replace("+00:00", "Z")

    def _now(self) -> datetime:
        current = self.now_provider()
        if current.tzinfo is None:
            return current.replace(tzinfo=timezone.utc)
        return current.astimezone(timezone.utc)

    def _parse_timestamp(self, value: str) -> datetime:
        parsed = datetime.fromisoformat(str(value or "").replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
