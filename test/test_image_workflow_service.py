from __future__ import annotations

import pytest

from services.image_service import ImageGenerationError
from services.image_workflow_service import ImageWorkflowService

MODEL_PRICE_CENTS = 100


class FakeQuotaGateway:
    def __init__(self) -> None:
        self.reserved: list[int] = []
        self.committed: list[str] = []
        self.released: list[str] = []

    def reserve_quota(self, amount_cents: int) -> str:
        self.reserved.append(amount_cents)
        return f"reservation-{amount_cents}"

    def commit_reservation(self, token: str) -> None:
        self.committed.append(token)

    def release_reservation(self, token: str) -> None:
        self.released.append(token)


class FakeBillingStore:
    def __init__(
        self,
        *,
        balances: dict[str, int] | None = None,
        fail_commit: bool = False,
        fail_release: bool = False,
    ) -> None:
        self.balances = dict(balances or {})
        self.reserved: dict[str, tuple[str, int, str, int]] = {}
        self.charges: list[tuple[str, int, str, int]] = []
        self.released: list[str] = []
        self.price_requests: list[str] = []
        self.fail_commit = fail_commit
        self.fail_release = fail_release

    def get_model_price_cents(self, model: str) -> int:
        self.price_requests.append(model)
        return MODEL_PRICE_CENTS

    def reserve_user_balance(self, *, user_id: str, amount_cents: int, model: str, count: int) -> str:
        balance = self.balances[user_id]
        reserved_total = sum(amount for owner, amount, _, _ in self.reserved.values() if owner == user_id)
        if balance - reserved_total < amount_cents:
            raise RuntimeError("public user balance is insufficient")
        token = f"user-reservation-{len(self.reserved) + 1}"
        self.reserved[token] = (user_id, amount_cents, model, count)
        return token

    def commit_user_balance_reservation(self, token: str) -> int:
        if self.fail_commit:
            raise RuntimeError("commit failed")
        user_id, amount_cents, model, count = self.reserved.pop(token)
        self.balances[user_id] -= amount_cents
        self.charges.append((user_id, amount_cents, model, count))
        return self.balances[user_id]

    def release_user_balance_reservation(self, token: str) -> None:
        if self.fail_release:
            raise RuntimeError("release failed")
        self.reserved.pop(token)
        self.released.append(token)

    def touch_user_balance_reservation(self, token: str) -> None:
        if token not in self.reserved:
            raise KeyError("user reservation not found")


class FakeImageBackend:
    def __init__(self, *, result: dict[str, object] | None = None, error: Exception | None = None) -> None:
        self.result = result or {"created": 1, "data": [{"b64_json": "abc"}]}
        self.error = error
        self.calls: list[tuple[str, tuple[object, ...]]] = []

    def generate_with_pool(self, prompt: str, model: str, n: int, response_format: str = "url") -> dict[str, object]:
        self.calls.append(("generate", (prompt, model, n, response_format)))
        if self.error is not None:
            raise self.error
        return self.result

    def edit_with_pool(self, prompt: str, images, model: str, n: int, response_format: str = "url") -> dict[str, object]:
        self.calls.append(("edit", (prompt, images, model, n, response_format)))
        if self.error is not None:
            raise self.error
        return self.result


def test_public_generation_commits_reserved_quota_on_success() -> None:
    quota = FakeQuotaGateway()
    billing = FakeBillingStore()
    backend = FakeImageBackend()
    service = ImageWorkflowService(quota_gateway=quota, billing_store=billing, image_backend=backend)

    result = service.generate_public(prompt="cat", model="gpt-image-1", n=2)

    assert result["data"] == [{"b64_json": "abc"}]
    assert quota.reserved == [200]
    assert quota.committed == ["reservation-200"]
    assert quota.released == []
    assert billing.charges == []


def test_public_generation_rolls_back_quota_on_failure() -> None:
    quota = FakeQuotaGateway()
    billing = FakeBillingStore()
    backend = FakeImageBackend(error=ImageGenerationError("boom"))
    service = ImageWorkflowService(quota_gateway=quota, billing_store=billing, image_backend=backend)

    with pytest.raises(ImageGenerationError):
        service.generate_public(prompt="cat", model="gpt-image-1", n=2)

    assert quota.reserved == [200]
    assert quota.committed == []
    assert quota.released == ["reservation-200"]
    assert billing.charges == []


def test_admin_generation_skips_public_quota() -> None:
    quota = FakeQuotaGateway()
    backend = FakeImageBackend()
    service = ImageWorkflowService(quota_gateway=quota, billing_store=None, image_backend=backend)

    result = service.generate_admin(prompt="cat", model="gpt-image-1", n=1)

    assert result["data"] == [{"b64_json": "abc"}]
    assert quota.reserved == []
    assert quota.committed == []
    assert quota.released == []


def test_authenticated_public_generation_uses_user_balance_not_public_panel() -> None:
    quota = FakeQuotaGateway()
    billing = FakeBillingStore(balances={"user-1": 500})
    backend = FakeImageBackend()
    service = ImageWorkflowService(quota_gateway=quota, billing_store=billing, image_backend=backend)

    result = service.generate_public(prompt="cat", model="gpt-image-1", n=2, public_user_id="user-1")

    assert result["data"] == [{"b64_json": "abc"}]
    assert quota.reserved == []
    assert quota.committed == []
    assert quota.released == []
    assert billing.charges == [("user-1", 200, "gpt-image-1", 2)]
    assert billing.balances["user-1"] == 300


def test_authenticated_public_generation_releases_user_reservation_on_failure() -> None:
    quota = FakeQuotaGateway()
    billing = FakeBillingStore(balances={"user-1": 500})
    backend = FakeImageBackend(error=ImageGenerationError("boom"))
    service = ImageWorkflowService(quota_gateway=quota, billing_store=billing, image_backend=backend)

    with pytest.raises(ImageGenerationError):
        service.generate_public(prompt="cat", model="gpt-image-1", n=2, public_user_id="user-1")

    assert quota.reserved == []
    assert quota.committed == []
    assert quota.released == []
    assert billing.charges == []
    assert billing.released == ["user-reservation-1"]
    assert billing.balances["user-1"] == 500


def test_authenticated_public_generation_surfaces_release_failure_after_operation_error() -> None:
    quota = FakeQuotaGateway()
    billing = FakeBillingStore(balances={"user-1": 500}, fail_release=True)
    backend = FakeImageBackend(error=ImageGenerationError("boom"))
    service = ImageWorkflowService(quota_gateway=quota, billing_store=billing, image_backend=backend)

    with pytest.raises(RuntimeError, match="public user reservation release failed after operation error"):
        service.generate_public(prompt="cat", model="gpt-image-1", n=2, public_user_id="user-1")

    assert billing.charges == []
    assert billing.reserved == {"user-reservation-1": ("user-1", 200, "gpt-image-1", 2)}


def test_authenticated_public_generation_fails_when_balance_is_insufficient() -> None:
    quota = FakeQuotaGateway()
    billing = FakeBillingStore(balances={"user-1": 100})
    backend = FakeImageBackend()
    service = ImageWorkflowService(quota_gateway=quota, billing_store=billing, image_backend=backend)

    with pytest.raises(RuntimeError, match="public user balance is insufficient"):
        service.generate_public(prompt="cat", model="gpt-image-1", n=2, public_user_id="user-1")

    assert quota.reserved == []
    assert quota.committed == []
    assert quota.released == []
    assert billing.charges == []
    assert billing.balances["user-1"] == 100
    assert backend.calls == []


def test_authenticated_public_generation_releases_reservation_when_commit_fails() -> None:
    quota = FakeQuotaGateway()
    billing = FakeBillingStore(balances={"user-1": 500}, fail_commit=True)
    backend = FakeImageBackend()
    service = ImageWorkflowService(quota_gateway=quota, billing_store=billing, image_backend=backend)

    with pytest.raises(RuntimeError, match="public user charge commit failed"):
        service.generate_public(prompt="cat", model="gpt-image-1", n=2, public_user_id="user-1")

    assert quota.reserved == []
    assert quota.committed == []
    assert quota.released == []
    assert billing.charges == []
    assert billing.released == ["user-reservation-1"]
    assert billing.balances["user-1"] == 500


def test_authenticated_public_generation_surfaces_release_failure_after_commit_error() -> None:
    quota = FakeQuotaGateway()
    billing = FakeBillingStore(balances={"user-1": 500}, fail_commit=True, fail_release=True)
    backend = FakeImageBackend()
    service = ImageWorkflowService(quota_gateway=quota, billing_store=billing, image_backend=backend)

    with pytest.raises(RuntimeError, match="public user charge commit failed and reservation release failed"):
        service.generate_public(prompt="cat", model="gpt-image-1", n=2, public_user_id="user-1")

    assert billing.charges == []
    assert billing.reserved == {"user-reservation-1": ("user-1", 200, "gpt-image-1", 2)}


def test_anonymous_public_generation_still_uses_public_panel_quota() -> None:
    quota = FakeQuotaGateway()
    billing = FakeBillingStore()
    backend = FakeImageBackend()
    service = ImageWorkflowService(quota_gateway=quota, billing_store=billing, image_backend=backend)

    service.generate_public(prompt="cat", model="gpt-image-1", n=2)

    assert quota.reserved == [200]
    assert quota.committed == ["reservation-200"]
    assert quota.released == []
    assert billing.charges == []
