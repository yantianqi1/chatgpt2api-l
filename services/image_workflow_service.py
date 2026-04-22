from __future__ import annotations

from typing import Iterable, Protocol


class ImageQuotaGateway(Protocol):
    def reserve_quota(self, count: int) -> str: ...

    def commit_reservation(self, token: str) -> object: ...

    def release_reservation(self, token: str) -> None: ...


class ImageBackend(Protocol):
    def generate_with_pool(self, prompt: str, model: str, n: int) -> dict[str, object]: ...

    def edit_with_pool(
        self,
        prompt: str,
        images: Iterable[tuple[bytes, str, str]],
        model: str,
        n: int,
    ) -> dict[str, object]: ...


class ImageWorkflowService:
    def __init__(self, *, quota_gateway: ImageQuotaGateway | None, image_backend: ImageBackend):
        self.quota_gateway = quota_gateway
        self.image_backend = image_backend

    def generate_admin(self, prompt: str, model: str, n: int) -> dict[str, object]:
        return self.image_backend.generate_with_pool(prompt, model, n)

    def edit_admin(
        self,
        prompt: str,
        images: Iterable[tuple[bytes, str, str]],
        model: str,
        n: int,
    ) -> dict[str, object]:
        return self.image_backend.edit_with_pool(prompt, images, model, n)

    def generate_public(self, prompt: str, model: str, n: int) -> dict[str, object]:
        return self._run_public(lambda: self.image_backend.generate_with_pool(prompt, model, n), n)

    def edit_public(
        self,
        prompt: str,
        images: Iterable[tuple[bytes, str, str]],
        model: str,
        n: int,
    ) -> dict[str, object]:
        return self._run_public(lambda: self.image_backend.edit_with_pool(prompt, images, model, n), n)

    def _run_public(self, operation, count: int) -> dict[str, object]:
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
