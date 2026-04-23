from __future__ import annotations

from threading import Event, Thread
from typing import Callable

from services.comic.models import ComicTask
from services.comic.tasks import (
    ComicTaskService,
    STATUS_COMPLETED,
    STATUS_COMPLETED_WITH_ERRORS,
    STATUS_FAILED,
    STATUS_QUEUED,
    STATUS_RUNNING,
)

DEFAULT_POLL_INTERVAL_SECONDS = 1
DEFAULT_STALE_AFTER_SECONDS = 300
THREAD_JOIN_TIMEOUT_SECONDS = 1


def _unconfigured_runner(_: ComicTask) -> dict[str, object]:
    raise RuntimeError("comic task runner is not configured")


class ComicWorker:
    def __init__(
        self,
        *,
        task_service: ComicTaskService,
        runner: Callable[[ComicTask], dict[str, object]] | None = None,
        poll_interval_seconds: int = DEFAULT_POLL_INTERVAL_SECONDS,
        stale_after_seconds: int = DEFAULT_STALE_AFTER_SECONDS,
    ):
        self.task_service = task_service
        self.runner = runner or _unconfigured_runner
        self.poll_interval_seconds = int(poll_interval_seconds)
        self.stale_after_seconds = int(stale_after_seconds)
        self._stop_event = Event()
        self._thread: Thread | None = None

    def start(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            return
        self.task_service.recover_stale_tasks(stale_after_seconds=self.stale_after_seconds)
        self._stop_event = Event()
        self._thread = Thread(target=self._run_loop, name="comic-worker", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        if self._thread is None:
            return
        self._stop_event.set()
        self._thread.join(timeout=THREAD_JOIN_TIMEOUT_SECONDS)
        self._thread = None

    def run_pending_once(self) -> None:
        for task in self.task_service.list_tasks():
            if task.status != STATUS_QUEUED:
                continue
            self._run_task(task)

    def _run_loop(self) -> None:
        while not self._stop_event.is_set():
            self.run_pending_once()
            self._stop_event.wait(self.poll_interval_seconds)

    def _run_task(self, task: ComicTask) -> None:
        running_task = self.task_service.update_task(
            task.id,
            status=STATUS_RUNNING,
            error=None,
            progress=task.progress,
        )
        try:
            result = self.runner(running_task)
        except Exception as exc:
            self.task_service.update_task(
                task.id,
                status=STATUS_FAILED,
                error=str(exc),
                progress=running_task.progress,
            )
            return
        errors = self._extract_errors(result)
        final_status = STATUS_COMPLETED_WITH_ERRORS if errors else STATUS_COMPLETED
        final_error = "; ".join(errors) if errors else None
        self.task_service.update_task(
            task.id,
            status=final_status,
            result_payload=result,
            error=final_error,
            progress=100,
        )

    def _extract_errors(self, result: dict[str, object]) -> list[str]:
        raw_errors = result.get("errors")
        if not isinstance(raw_errors, list):
            return []
        return [str(error).strip() for error in raw_errors if str(error).strip()]
