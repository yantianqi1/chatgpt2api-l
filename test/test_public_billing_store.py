from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

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
    assert "password_hash" not in user


def test_store_rejects_non_integer_signup_bonus_cents(tmp_path: Path) -> None:
    store = PublicBillingStore(tmp_path / "public_billing.db")

    with pytest.raises(TypeError, match="signup_bonus_cents must be an int"):
        store.create_user(username="demo", password_hash="hash", signup_bonus_cents="100")


def test_store_reopen_keeps_seed_rows_and_persists_ledger(tmp_path: Path) -> None:
    db_file = tmp_path / "public_billing.db"

    first_store = PublicBillingStore(db_file)
    first_store.create_user(username="demo", password_hash="hash", signup_bonus_cents=100)

    second_store = PublicBillingStore(db_file)
    prices = second_store.list_model_pricing()

    with sqlite3.connect(db_file) as conn:
        price_count = conn.execute("SELECT COUNT(*) FROM model_pricing").fetchone()[0]
        ledger_row = conn.execute(
            """
            SELECT scope, user_id, change_cents, balance_after_cents, reason, reference_type, reference_id
            FROM quota_ledger
            ORDER BY id
            """
        ).fetchone()

    assert [item["model"] for item in prices] == ["gpt-image-1", "gpt-image-2"]
    assert price_count == 2
    assert ledger_row == ("user", 1, 100, 100, "signup_bonus", "user", "1")
