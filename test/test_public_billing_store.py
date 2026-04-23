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


def test_store_rejects_negative_signup_bonus_cents(tmp_path: Path) -> None:
    store = PublicBillingStore(tmp_path / "public_billing.db")

    with pytest.raises(ValueError, match="signup_bonus_cents must be greater than or equal to 0"):
        store.create_user(username="demo", password_hash="hash", signup_bonus_cents=-100)


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


def test_store_rejects_negative_money_columns_at_db_level(tmp_path: Path) -> None:
    db_file = tmp_path / "public_billing.db"
    store = PublicBillingStore(db_file)

    with sqlite3.connect(db_file) as conn:
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                """
                INSERT INTO users (username, password_hash, balance_cents, status, created_at, updated_at)
                VALUES ('bad-user', 'hash', -1, 'active', 'now', 'now')
                """
            )
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                """
                INSERT INTO activation_codes (code, amount_cents, batch_note, status, created_at)
                VALUES ('code-1', -1, 'note', 'unused', 'now')
                """
            )
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                """
                INSERT INTO quota_ledger (
                    scope, user_id, change_cents, balance_after_cents, reason,
                    reference_type, reference_id, created_at
                )
                VALUES ('user', NULL, -1, -1, 'signup_bonus', 'user', '1', 'now')
                """
            )
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                """
                INSERT INTO model_pricing (model, price_cents, enabled, updated_at)
                VALUES ('gpt-image-x', -1, 1, 'now')
                """
            )


def test_store_indexes_session_token_hash(tmp_path: Path) -> None:
    db_file = tmp_path / "public_billing.db"
    PublicBillingStore(db_file)

    with sqlite3.connect(db_file) as conn:
        index_rows = conn.execute("PRAGMA index_list('user_sessions')").fetchall()

    assert any("token_hash" in str(index_row[1]) for index_row in index_rows)
