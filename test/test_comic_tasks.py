from __future__ import annotations

import json
from contextlib import contextmanager
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from importlib import import_module
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from services.config import config


def _load_module(module_name: str):
    try:
        return import_module(module_name)
    except ModuleNotFoundError as exc:
        pytest.fail(f"missing module {module_name}: {exc}")


@contextmanager
def with_comic_projects_dir(path: Path):
    original = config.comic_projects_dir
    object.__setattr__(config, "comic_projects_dir", path)
    try:
        yield
    finally:
        object.__setattr__(config, "comic_projects_dir", original)


def _create_store(tmp_path: Path):
    store_module = _load_module("services.comic.store")
    return store_module.ComicProjectStore(tmp_path / "comic-projects")


def _create_project(store):
    return store.create_project(
        title="银河列车",
        source_text="第一章：列车驶入暴风区。",
        style_prompt="赛博都市漫画",
    )


def test_create_task_saves_queued_task_file(tmp_path: Path) -> None:
    tasks_module = _load_module("services.comic.tasks")
    store = _create_store(tmp_path)
    project = _create_project(store)
    service = tasks_module.ComicTaskService(store)

    task = service.create_task(
        project_id=project.id,
        kind="render_scene",
        target_id="scene-1",
        input_payload={"scene_id": "scene-1"},
    )

    task_file = tmp_path / "comic-projects" / project.id / "tasks" / f"{task.id}.json"
    assert task.status == tasks_module.STATUS_QUEUED
    assert task.progress == 0
    payload = json.loads(task_file.read_text(encoding="utf-8"))
    assert payload["status"] == tasks_module.STATUS_QUEUED
    assert payload["progress"] == 0


def test_worker_marks_task_running_before_handler_execution(tmp_path: Path) -> None:
    tasks_module = _load_module("services.comic.tasks")
    worker_module = _load_module("services.comic.worker")
    store = _create_store(tmp_path)
    project = _create_project(store)
    service = tasks_module.ComicTaskService(store)
    task = service.create_task(
        project_id=project.id,
        kind="render_scene",
        target_id="scene-1",
        input_payload={"scene_id": "scene-1"},
    )
    observed_statuses: list[str] = []

    def runner(current_task):
        observed_statuses.append(service.get_task(current_task.id).status)
        return {"assets": [{"scene_id": "scene-1"}]}

    worker = worker_module.ComicWorker(task_service=service, runner=runner, poll_interval_seconds=60)

    worker.run_pending_once()

    assert observed_statuses == [tasks_module.STATUS_RUNNING]
    assert service.get_task(task.id).status == tasks_module.STATUS_COMPLETED


def test_successful_task_ends_as_completed(tmp_path: Path) -> None:
    tasks_module = _load_module("services.comic.tasks")
    worker_module = _load_module("services.comic.worker")
    store = _create_store(tmp_path)
    project = _create_project(store)
    service = tasks_module.ComicTaskService(store)
    task = service.create_task(
        project_id=project.id,
        kind="render_scene",
        target_id="scene-1",
        input_payload={"scene_id": "scene-1"},
    )
    worker = worker_module.ComicWorker(
        task_service=service,
        runner=lambda _: {"assets": [{"scene_id": "scene-1"}]},
        poll_interval_seconds=60,
    )

    worker.run_pending_once()

    updated = service.get_task(task.id)
    assert updated.status == tasks_module.STATUS_COMPLETED
    assert updated.error is None
    assert updated.progress == 100


def test_partial_batch_render_ends_as_completed_with_errors(tmp_path: Path) -> None:
    tasks_module = _load_module("services.comic.tasks")
    worker_module = _load_module("services.comic.worker")
    store = _create_store(tmp_path)
    project = _create_project(store)
    service = tasks_module.ComicTaskService(store)
    task = service.create_task(
        project_id=project.id,
        kind="render_batch",
        target_id="chapter-1",
        input_payload={"chapter_id": "chapter-1"},
    )
    worker = worker_module.ComicWorker(
        task_service=service,
        runner=lambda _: {"assets": [{"scene_id": "scene-1"}], "errors": ["scene-2 failed"]},
        poll_interval_seconds=60,
    )

    worker.run_pending_once()

    updated = service.get_task(task.id)
    assert updated.status == tasks_module.STATUS_COMPLETED_WITH_ERRORS
    assert updated.error == "scene-2 failed"
    assert updated.result_payload == {"assets": [{"scene_id": "scene-1"}], "errors": ["scene-2 failed"]}


def test_worker_startup_recovery_marks_stale_running_tasks_failed(tmp_path: Path) -> None:
    tasks_module = _load_module("services.comic.tasks")
    worker_module = _load_module("services.comic.worker")
    store = _create_store(tmp_path)
    project = _create_project(store)
    current_time = datetime(2026, 4, 23, 9, 0, tzinfo=timezone.utc)
    service = tasks_module.ComicTaskService(store, now_provider=lambda: current_time)
    task = service.create_task(
        project_id=project.id,
        kind="render_scene",
        target_id="scene-1",
        input_payload={"scene_id": "scene-1"},
    )
    stale_task = replace(
        task,
        status=tasks_module.STATUS_RUNNING,
        progress=50,
        updated_at=(current_time - timedelta(minutes=10)).isoformat().replace("+00:00", "Z"),
    )
    store.save_task(project.id, stale_task)
    worker = worker_module.ComicWorker(
        task_service=service,
        runner=lambda _: {"assets": []},
        poll_interval_seconds=60,
        stale_after_seconds=60,
    )

    worker.start()
    worker.stop()

    recovered = service.get_task(task.id)
    assert recovered.status == tasks_module.STATUS_FAILED
    assert recovered.error == "task became stale while worker was offline"


def test_create_app_starts_and_stops_comic_worker(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    api_module = _load_module("services.api")
    events: list[object] = []

    class FakeWatcherThread:
        def join(self, timeout: float | None = None) -> None:
            events.append(("watcher-join", timeout))

    class FakeComicWorker:
        def __init__(self, *args, **kwargs) -> None:
            events.append(("worker-init", bool(args), bool(kwargs)))

        def start(self) -> None:
            events.append("worker-start")

        def stop(self) -> None:
            events.append("worker-stop")

    monkeypatch.setattr(api_module, "start_limited_account_watcher", lambda stop_event: FakeWatcherThread())
    monkeypatch.setattr(api_module, "ComicWorker", FakeComicWorker)

    with with_comic_projects_dir(tmp_path / "comic-projects"):
        with TestClient(api_module.create_app()):
            pass

    assert "worker-start" in events
    assert "worker-stop" in events
