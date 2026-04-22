from __future__ import annotations

import pytest

from services.image_workflow_service import ImageWorkflowService


class FakeQuotaGateway:
    def __init__(self) -> None:
        self.reserved: list[int] = []
        self.committed: list[str] = []
        self.released: list[str] = []

    def reserve_quota(self, count: int) -> str:
        self.reserved.append(count)
        return f"reservation-{count}"

    def commit_reservation(self, token: str) -> None:
        self.committed.append(token)

    def release_reservation(self, token: str) -> None:
        self.released.append(token)


class FakeImageBackend:
    def __init__(self, *, result: dict[str, object] | None = None, error: Exception | None = None) -> None:
        self.result = result or {"created": 1, "data": [{"url": "https://img.example.com/generated-images/abc.png"}]}
        self.error = error

    def generate_with_pool(self, prompt: str, model: str, n: int, response_format: str) -> dict[str, object]:
        if self.error is not None:
            raise self.error
        return self.result


def test_public_generation_commits_reserved_quota_on_success() -> None:
    quota = FakeQuotaGateway()
    backend = FakeImageBackend()
    service = ImageWorkflowService(quota_gateway=quota, image_backend=backend)

    result = service.generate_public(prompt="cat", model="gpt-image-1", n=2, response_format="url")

    assert result["data"] == [{"url": "https://img.example.com/generated-images/abc.png"}]
    assert quota.reserved == [2]
    assert quota.committed == ["reservation-2"]
    assert quota.released == []


def test_public_generation_rolls_back_quota_on_failure() -> None:
    quota = FakeQuotaGateway()
    backend = FakeImageBackend(error=RuntimeError("boom"))
    service = ImageWorkflowService(quota_gateway=quota, image_backend=backend)

    with pytest.raises(RuntimeError):
        service.generate_public(prompt="cat", model="gpt-image-1", n=2, response_format="url")

    assert quota.reserved == [2]
    assert quota.committed == []
    assert quota.released == ["reservation-2"]


def test_admin_generation_skips_public_quota() -> None:
    quota = FakeQuotaGateway()
    backend = FakeImageBackend()
    service = ImageWorkflowService(quota_gateway=quota, image_backend=backend)

    result = service.generate_admin(prompt="cat", model="gpt-image-1", n=1, response_format="url")

    assert result["data"] == [{"url": "https://img.example.com/generated-images/abc.png"}]
    assert quota.reserved == []
    assert quota.committed == []
    assert quota.released == []
