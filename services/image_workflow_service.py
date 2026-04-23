from __future__ import annotations

from typing import Iterable, Protocol

from services.public_money import compute_cost_cents


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


class PublicBillingStore(Protocol):
    def get_model_price_cents(self, model: str) -> int: ...

    def get_user_balance_cents(self, user_id: str) -> int: ...

    def debit_user_balance(self, *, user_id: str, amount_cents: int, model: str, count: int) -> int: ...


class ImageWorkflowService:
    def __init__(
        self,
        *,
        quota_gateway: ImageQuotaGateway | None,
        billing_store: PublicBillingStore | None,
        image_backend: ImageBackend,
    ):
        self.quota_gateway = quota_gateway
        self.billing_store = billing_store
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

    def generate_public(
        self,
        prompt: str,
        model: str,
        n: int,
        public_user_id: str | None = None,
    ) -> dict[str, object]:
        return self._run_public(
            lambda: self.image_backend.generate_with_pool(prompt, model, n),
            model=model,
            count=n,
            public_user_id=public_user_id,
        )

    def edit_public(
        self,
        prompt: str,
        images: Iterable[tuple[bytes, str, str]],
        model: str,
        n: int,
        public_user_id: str | None = None,
    ) -> dict[str, object]:
        return self._run_public(
            lambda: self.image_backend.edit_with_pool(prompt, images, model, n),
            model=model,
            count=n,
            public_user_id=public_user_id,
        )

    def _run_public(self, operation, *, model: str, count: int, public_user_id: str | None) -> dict[str, object]:
        cost_cents = self._compute_cost_cents(model, count)
        if public_user_id:
            return self._run_authenticated_public(
                operation,
                model=model,
                count=count,
                cost_cents=cost_cents,
                user_id=public_user_id,
            )
        return self._run_anonymous_public(operation, cost_cents)

    def _run_anonymous_public(self, operation, cost_cents: int) -> dict[str, object]:
        if self.quota_gateway is None:
            raise RuntimeError("public quota gateway is not configured")
        reservation = self.quota_gateway.reserve_quota(cost_cents)
        try:
            result = operation()
        except Exception:
            self.quota_gateway.release_reservation(reservation)
            raise
        self.quota_gateway.commit_reservation(reservation)
        return result

    def _run_authenticated_public(
        self,
        operation,
        *,
        model: str,
        count: int,
        cost_cents: int,
        user_id: str,
    ) -> dict[str, object]:
        if self.billing_store is None:
            raise RuntimeError("public billing store is not configured")
        if self.billing_store.get_user_balance_cents(user_id) < cost_cents:
            raise RuntimeError("public user balance is insufficient")
        result = operation()
        self.billing_store.debit_user_balance(
            user_id=user_id,
            amount_cents=cost_cents,
            model=model,
            count=count,
        )
        return result

    def _compute_cost_cents(self, model: str, count: int) -> int:
        if self.billing_store is None:
            raise RuntimeError("public billing store is not configured")
        return compute_cost_cents(
            price_cents=self.billing_store.get_model_price_cents(model),
            count=count,
        )
