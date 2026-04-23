from __future__ import annotations

from contextlib import contextmanager
from threading import Condition
from typing import ContextManager, Iterable, Protocol

from services.config import get_image_settings


class ImageQuotaGateway(Protocol):
    def reserve_quota(self, count: int) -> str: ...

    def commit_reservation(self, token: str) -> object: ...

    def release_reservation(self, token: str) -> None: ...


class ImageBackend(Protocol):
    def generate_with_pool(self, prompt: str, model: str, n: int, response_format: str) -> dict[str, object]: ...

    def edit_with_pool(
        self,
        prompt: str,
        images: Iterable[tuple[bytes, str, str]],
        model: str,
        n: int,
        response_format: str,
    ) -> dict[str, object]: ...


class PublicImageLimiter(Protocol):
    def acquire(self) -> ContextManager[None]: ...


class ImageJobLimiter:
    def __init__(self) -> None:
        self._active_jobs = 0
        self._condition = Condition()

    @contextmanager
    def acquire(self) -> ContextManager[None]:
        with self._condition:
            while self._active_jobs >= get_image_settings().max_concurrent_jobs:
                self._condition.wait(timeout=0.2)
            self._active_jobs += 1
        try:
            yield
        finally:
            with self._condition:
                self._active_jobs = max(0, self._active_jobs - 1)
                self._condition.notify_all()


class ImageWorkflowService:
    def __init__(
        self,
        *,
        quota_gateway: ImageQuotaGateway | None,
        image_backend: ImageBackend,
        public_image_limiter: PublicImageLimiter | None = None,
    ):
        self.quota_gateway = quota_gateway
        self.image_backend = image_backend
        self.public_image_limiter = public_image_limiter

    def generate_admin(self, prompt: str, model: str, n: int, response_format: str) -> dict[str, object]:
        return self.image_backend.generate_with_pool(prompt, model, n, response_format)

    def edit_admin(
        self,
        prompt: str,
        images: Iterable[tuple[bytes, str, str]],
        model: str,
        n: int,
        response_format: str,
    ) -> dict[str, object]:
        return self.image_backend.edit_with_pool(prompt, images, model, n, response_format)

    def generate_public(self, prompt: str, model: str, n: int, response_format: str) -> dict[str, object]:
        return self._run_public(lambda: self.image_backend.generate_with_pool(prompt, model, n, response_format), n)

    def edit_public(
        self,
        prompt: str,
        images: Iterable[tuple[bytes, str, str]],
        model: str,
        n: int,
        response_format: str,
    ) -> dict[str, object]:
        return self._run_public(lambda: self.image_backend.edit_with_pool(prompt, images, model, n, response_format), n)

    def _run_public(self, operation, count: int) -> dict[str, object]:
        with self._acquire_public_limiter():
            if self.quota_gateway is None:
                raise RuntimeError("public quota gateway is not configured")
            reservation = self.quota_gateway.reserve_quota(count)
            try:
                result = operation()
            except Exception:
                self.quota_gateway.release_reservation(reservation)
                raise
            self.quota_gateway.commit_reservation(reservation)
            return result

    @contextmanager
    def _acquire_public_limiter(self):
        if self.public_image_limiter is None:
            yield
            return
        with self.public_image_limiter.acquire():
            yield
