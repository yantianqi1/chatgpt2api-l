from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path

from fastapi.testclient import TestClient

from services.api import create_app
from services.config import config
from services.public_billing_store import PublicBillingStore


@contextmanager
def with_public_billing_file(path: Path):
    original = config.public_billing_file
    object.__setattr__(config, "public_billing_file", path)
    try:
        yield
    finally:
        object.__setattr__(config, "public_billing_file", original)


def admin_headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {config.auth_key}"}


def test_admin_can_list_model_pricing(tmp_path: Path) -> None:
    with with_public_billing_file(tmp_path / "public_billing.db"):
        client = TestClient(create_app(), base_url="https://testserver")
        response = client.get("/api/admin/billing/model-pricing", headers=admin_headers())

    assert response.status_code == 200
    assert response.json()["items"][0]["model"] == "gpt-image-1"


def test_admin_billing_routes_require_auth(tmp_path: Path) -> None:
    with with_public_billing_file(tmp_path / "public_billing.db"):
        client = TestClient(create_app(), base_url="https://testserver")
        response = client.get("/api/admin/billing/model-pricing")

    assert response.status_code == 401


def test_admin_can_update_model_pricing(tmp_path: Path) -> None:
    db_file = tmp_path / "public_billing.db"
    store = PublicBillingStore(db_file)
    assert store.list_model_pricing()[0]["price"] == "1.00"

    with with_public_billing_file(db_file):
        client = TestClient(create_app(), base_url="https://testserver")
        response = client.post(
            "/api/admin/billing/model-pricing",
            headers=admin_headers(),
            json={"model": "gpt-image-1", "price": "2.50", "enabled": False},
        )

    assert response.status_code == 200
    assert response.json()["items"][0]["price"] == "2.50"
    assert response.json()["items"][0]["enabled"] == "0"

    reloaded = PublicBillingStore(db_file).list_model_pricing()
    assert reloaded[0]["price"] == "2.50"
    assert reloaded[0]["enabled"] == "0"


def test_admin_update_model_pricing_returns_404_for_unknown_model(tmp_path: Path) -> None:
    with with_public_billing_file(tmp_path / "public_billing.db"):
        client = TestClient(create_app(), base_url="https://testserver")
        response = client.post(
            "/api/admin/billing/model-pricing",
            headers=admin_headers(),
            json={"model": "unknown-model", "price": "2.50", "enabled": False},
        )

    assert response.status_code == 404


def test_admin_can_batch_generate_activation_codes(tmp_path: Path) -> None:
    db_file = tmp_path / "public_billing.db"

    with with_public_billing_file(db_file):
        client = TestClient(create_app(), base_url="https://testserver")
        response = client.post(
            "/api/admin/billing/activation-codes",
            headers=admin_headers(),
            json={"count": 2, "amount": "5.50", "batch_note": "spring"},
        )

    assert response.status_code == 200
    payload = response.json()
    assert len(payload["items"]) == 2
    assert payload["items"][0]["amount"] == "5.50"
    assert payload["items"][0]["batch_note"] == "spring"
    assert len(payload["items"][0]["code"]) == 32

    with with_public_billing_file(db_file):
        client = TestClient(create_app(), base_url="https://testserver")
        list_response = client.get("/api/admin/billing/activation-codes", headers=admin_headers())

    assert list_response.status_code == 200
    assert len(list_response.json()["items"]) == 2


def test_admin_store_helpers_cover_model_pricing_and_activation_codes(tmp_path: Path) -> None:
    store = PublicBillingStore(tmp_path / "public_billing.db")

    updated = store.update_model_pricing(model="gpt-image-1", price_cents=250, enabled=False)
    codes = store.list_activation_codes()

    assert updated[0]["price"] == "2.50"
    assert updated[0]["enabled"] == "0"
    assert codes == []
