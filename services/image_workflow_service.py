from __future__ import annotations

from threading import Event, Thread
from typing import Iterable, Protocol

from services.public_money import compute_cost_cents

USER_BALANCE_RESERVATION_HEARTBEAT_SECONDS = 60


class ImageQuotaGateway(Protocol):
    def reserve_quota(self, amount_cents: int) -> str: ...

    def commit_reservation(self, token: str) -> object: ...

    def release_reservation(self, token: str) -> None: ...


class ImageBackend(Protocol):
    def generate_with_pool(
        self,
        prompt: str,
        model: str,
        n: int,
        response_format: str = "url",
    ) -> dict[str, object]: ...

    def edit_with_pool(
        self,
        prompt: str,
        images: Iterable[tuple[bytes, str, str]],
        model: str,
        n: int,
        response_format: str = "url",
    ) -> dict[str, object]: ...


class PublicBillingStore(Protocol):
    def get_model_price_cents(self, model: str) -> int: ...

    def reserve_user_balance(self, *, user_id: str, amount_cents: int, model: str, count: int) -> str: ...

    def commit_user_balance_reservation(self, token: str) -> int: ...

    def release_user_balance_reservation(self, token: str) -> None: ...

    def touch_user_balance_reservation(self, token: str) -> None: ...


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

    def generate_admin(
        self,
        prompt: str,
        model: str,
        n: int,
        response_format: str = "url",
    ) -> dict[str, object]:
        return self.image_backend.generate_with_pool(prompt, model, n, response_format)

    def edit_admin(
        self,
        prompt: str,
        images: Iterable[tuple[bytes, str, str]],
        model: str,
        n: int,
        response_format: str = "url",
    ) -> dict[str, object]:
        return self.image_backend.edit_with_pool(prompt, images, model, n, response_format)

    def generate_public(
        self,
        prompt: str,
        model: str,
        n: int,
        response_format: str = "url",
        public_user_id: str | None = None,
    ) -> dict[str, object]:
        return self._run_public(
            lambda: self.image_backend.generate_with_pool(prompt, model, n, response_format),
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
        response_format: str = "url",
        public_user_id: str | None = None,
    ) -> dict[str, object]:
        return self._run_public(
            lambda: self.image_backend.edit_with_pool(prompt, images, model, n, response_format),
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

    def _run_anonymous_public(self, operation, amount_cents: int) -> dict[str, object]:
        if self.quota_gateway is None:
            raise RuntimeError("public quota gateway is not configured")
        reservation = self.quota_gateway.reserve_quota(amount_cents)
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
        reservation = self.billing_store.reserve_user_balance(
            user_id=user_id,
            amount_cents=cost_cents,
            model=model,
            count=count,
        )
        heartbeat_stop = Event()
        heartbeat_errors: list[Exception] = []
        heartbeat = Thread(
            target=self._heartbeat_user_reservation,
            args=(reservation, heartbeat_stop, heartbeat_errors),
            daemon=True,
        )
        heartbeat.start()
        try:
            result = operation()
        except Exception:
            heartbeat_stop.set()
            heartbeat.join(timeout=1)
            try:
                self.billing_store.release_user_balance_reservation(reservation)
            except Exception as release_exc:
                raise RuntimeError("public user reservation release failed after operation error") from release_exc
            raise
        heartbeat_stop.set()
        heartbeat.join(timeout=1)
        if heartbeat_errors:
            try:
                self.billing_store.release_user_balance_reservation(reservation)
            except Exception as release_exc:
                raise RuntimeError("public user reservation heartbeat failed and release failed") from release_exc
            raise RuntimeError("public user reservation heartbeat failed") from heartbeat_errors[0]
        try:
            self.billing_store.commit_user_balance_reservation(reservation)
        except Exception as exc:
            try:
                self.billing_store.release_user_balance_reservation(reservation)
            except Exception as release_exc:
                raise RuntimeError("public user charge commit failed and reservation release failed") from release_exc
            raise RuntimeError("public user charge commit failed") from exc
        return result

    def _compute_cost_cents(self, model: str, count: int) -> int:
        if self.billing_store is None:
            raise RuntimeError("public billing store is not configured")
        return compute_cost_cents(
            price_cents=self.billing_store.get_model_price_cents(model),
            count=count,
        )

    def _heartbeat_user_reservation(self, token: str, stop_event: Event, errors: list[Exception]) -> None:
        while not stop_event.wait(USER_BALANCE_RESERVATION_HEARTBEAT_SECONDS):
            try:
                if self.billing_store is None:
                    raise RuntimeError("public billing store is not configured")
                self.billing_store.touch_user_balance_reservation(token)
            except Exception as exc:
                errors.append(exc)
                stop_event.set()
                return
