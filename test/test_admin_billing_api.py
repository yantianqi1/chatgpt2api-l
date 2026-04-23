from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
import subprocess
import sys

from fastapi.testclient import TestClient

from services.api import create_app
from services.config import config
from services.public_auth_service import PublicAuthService
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


def test_create_app_import_does_not_require_curl_cffi_at_import_time() -> None:
    project_root = Path(__file__).resolve().parents[1]
    code = """
import builtins

real_import = builtins.__import__

def blocked_import(name, globals=None, locals=None, fromlist=(), level=0):
    if name.startswith("curl_cffi"):
        raise ModuleNotFoundError("No module named 'curl_cffi'")
    return real_import(name, globals, locals, fromlist, level)

builtins.__import__ = blocked_import

from services.api import create_app

create_app()
"""
    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=project_root,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr


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


def test_admin_update_model_pricing_rejects_invalid_price(tmp_path: Path) -> None:
    with with_public_billing_file(tmp_path / "public_billing.db"):
        client = TestClient(create_app(), base_url="https://testserver")
        response = client.post(
            "/api/admin/billing/model-pricing",
            headers=admin_headers(),
            json={"model": "gpt-image-1", "price": "bad", "enabled": True},
        )

    assert response.status_code == 400


def test_admin_update_model_pricing_rejects_negative_price(tmp_path: Path) -> None:
    with with_public_billing_file(tmp_path / "public_billing.db"):
        client = TestClient(create_app(), base_url="https://testserver")
        response = client.post(
            "/api/admin/billing/model-pricing",
            headers=admin_headers(),
            json={"model": "gpt-image-1", "price": "-1.00", "enabled": True},
        )

    assert response.status_code == 400


def test_admin_create_activation_codes_rejects_invalid_amount(tmp_path: Path) -> None:
    with with_public_billing_file(tmp_path / "public_billing.db"):
        client = TestClient(create_app(), base_url="https://testserver")
        response = client.post(
            "/api/admin/billing/activation-codes",
            headers=admin_headers(),
            json={"count": 2, "amount": "bad", "batch_note": "spring"},
        )

    assert response.status_code == 400


def test_admin_create_activation_codes_rejects_negative_amount(tmp_path: Path) -> None:
    with with_public_billing_file(tmp_path / "public_billing.db"):
        client = TestClient(create_app(), base_url="https://testserver")
        response = client.post(
            "/api/admin/billing/activation-codes",
            headers=admin_headers(),
            json={"count": 2, "amount": "-1.00", "batch_note": "spring"},
        )

    assert response.status_code == 400


def test_admin_update_model_pricing_rejects_blank_model(tmp_path: Path) -> None:
    with with_public_billing_file(tmp_path / "public_billing.db"):
        client = TestClient(create_app(), base_url="https://testserver")
        response = client.post(
            "/api/admin/billing/model-pricing",
            headers=admin_headers(),
            json={"model": "   ", "price": "2.50", "enabled": True},
        )

    assert response.status_code == 400


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


def test_admin_activation_codes_can_filter_by_status(tmp_path: Path) -> None:
    db_file = tmp_path / "public_billing.db"
    store = PublicBillingStore(db_file)
    user = store.create_user(username="demo", password_hash="hash", signup_bonus_cents=0)
    code = store.create_activation_codes(count=1, amount_cents=550, batch_note="spring")[0]["code"]
    auth_service = PublicAuthService(store)
    auth_service.redeem_activation_code(code=code, user_id=user["id"])

    with with_public_billing_file(db_file):
        client = TestClient(create_app(), base_url="https://testserver")
        unused_response = client.get(
            "/api/admin/billing/activation-codes",
            headers=admin_headers(),
            params={"status": "unused"},
        )
        redeemed_response = client.get(
            "/api/admin/billing/activation-codes",
            headers=admin_headers(),
            params={"status": "redeemed"},
        )

    assert unused_response.status_code == 200
    assert all(item["status"] == "unused" for item in unused_response.json()["items"])
    assert redeemed_response.status_code == 200
    assert all(item["status"] == "redeemed" for item in redeemed_response.json()["items"])


def test_admin_activation_codes_can_filter_by_batch_note(tmp_path: Path) -> None:
    db_file = tmp_path / "public_billing.db"
    store = PublicBillingStore(db_file)
    store.create_activation_codes(count=1, amount_cents=550, batch_note="spring")
    store.create_activation_codes(count=1, amount_cents=550, batch_note="summer")

    with with_public_billing_file(db_file):
        client = TestClient(create_app(), base_url="https://testserver")
        response = client.get(
            "/api/admin/billing/activation-codes",
            headers=admin_headers(),
            params={"batch_note": "spring"},
        )

    assert response.status_code == 200
    assert {item["batch_note"] for item in response.json()["items"]} == {"spring"}


def test_admin_activation_codes_can_search_by_partial_batch_note(tmp_path: Path) -> None:
    db_file = tmp_path / "public_billing.db"
    store = PublicBillingStore(db_file)
    store.create_activation_codes(count=1, amount_cents=550, batch_note="spring")
    store.create_activation_codes(count=1, amount_cents=550, batch_note="summer")

    with with_public_billing_file(db_file):
        client = TestClient(create_app(), base_url="https://testserver")
        response = client.get(
            "/api/admin/billing/activation-codes",
            headers=admin_headers(),
            params={"batch_note": "spr"},
        )

    assert response.status_code == 200
    assert {item["batch_note"] for item in response.json()["items"]} == {"spring"}


def test_admin_activation_codes_can_filter_empty_batch_note(tmp_path: Path) -> None:
    db_file = tmp_path / "public_billing.db"
    store = PublicBillingStore(db_file)
    store.create_activation_codes(count=1, amount_cents=550, batch_note="")
    store.create_activation_codes(count=1, amount_cents=550, batch_note="spring")

    with with_public_billing_file(db_file):
        client = TestClient(create_app(), base_url="https://testserver")
        response = client.get(
            "/api/admin/billing/activation-codes",
            headers=admin_headers(),
            params={"batch_note": ""},
        )

    assert response.status_code == 200
    assert len(response.json()["items"]) == 1
    assert response.json()["items"][0]["batch_note"] == ""


def test_admin_activation_codes_can_filter_by_redeemed_username(tmp_path: Path) -> None:
    db_file = tmp_path / "public_billing.db"
    store = PublicBillingStore(db_file)
    auth_service = PublicAuthService(store)
    alice = store.create_user(username="alice", password_hash="hash", signup_bonus_cents=0)
    bob = store.create_user(username="bob", password_hash="hash", signup_bonus_cents=0)
    alice_code = store.create_activation_codes(count=1, amount_cents=550, batch_note="spring")[0]["code"]
    bob_code = store.create_activation_codes(count=1, amount_cents=550, batch_note="spring")[0]["code"]
    auth_service.redeem_activation_code(code=alice_code, user_id=alice["id"])
    auth_service.redeem_activation_code(code=bob_code, user_id=bob["id"])

    with with_public_billing_file(db_file):
        client = TestClient(create_app(), base_url="https://testserver")
        response = client.get(
            "/api/admin/billing/activation-codes",
            headers=admin_headers(),
            params={"redeemed_username": "alice"},
        )

    assert response.status_code == 200
    assert {item["redeemed_by_user_id"] for item in response.json()["items"]} == {alice["id"]}


def test_admin_activation_codes_can_search_by_partial_redeemed_username(tmp_path: Path) -> None:
    db_file = tmp_path / "public_billing.db"
    store = PublicBillingStore(db_file)
    auth_service = PublicAuthService(store)
    demo = store.create_user(username="demo", password_hash="hash", signup_bonus_cents=0)
    other = store.create_user(username="other", password_hash="hash", signup_bonus_cents=0)
    demo_code = store.create_activation_codes(count=1, amount_cents=550, batch_note="spring")[0]["code"]
    other_code = store.create_activation_codes(count=1, amount_cents=550, batch_note="spring")[0]["code"]
    auth_service.redeem_activation_code(code=demo_code, user_id=demo["id"])
    auth_service.redeem_activation_code(code=other_code, user_id=other["id"])

    with with_public_billing_file(db_file):
        client = TestClient(create_app(), base_url="https://testserver")
        response = client.get(
            "/api/admin/billing/activation-codes",
            headers=admin_headers(),
            params={"redeemed_username": "de"},
        )

    assert response.status_code == 200
    assert {item["redeemed_by_user_id"] for item in response.json()["items"]} == {demo["id"]}


def test_admin_store_helpers_cover_model_pricing_and_activation_codes(tmp_path: Path) -> None:
    store = PublicBillingStore(tmp_path / "public_billing.db")

    updated = store.update_model_pricing(model="gpt-image-1", price_cents=250, enabled=False)
    codes = store.list_activation_codes()
    generated_code = store.create_activation_codes(count=1, amount_cents=550, batch_note="spring")[0]

    assert updated[0]["price"] == "2.50"
    assert updated[0]["enabled"] == "0"
    assert generated_code["amount_cents"] == 550
    assert "amount" not in generated_code
    assert codes == []
