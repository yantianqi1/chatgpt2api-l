from __future__ import annotations

from pathlib import Path

from services.public_billing_store import PublicBillingStore


def test_store_bootstraps_default_model_prices(tmp_path: Path) -> None:
    store = PublicBillingStore(tmp_path / "public_billing.db")

    prices = store.list_model_pricing()

    assert [item["model"] for item in prices] == ["gpt-image-1", "gpt-image-2"]
    assert prices[0]["price"] == "1.00"


def test_store_creates_user_with_signup_bonus(tmp_path: Path) -> None:
    store = PublicBillingStore(tmp_path / "public_billing.db")

    user = store.create_user(username="demo", password_hash="hash", signup_bonus_cents=100)

    assert user["username"] == "demo"
    assert user["balance"] == "1.00"
