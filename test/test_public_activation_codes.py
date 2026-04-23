from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from services.public_auth_service import PublicAuthService
from services.public_billing_store import PublicBillingStore


def test_generate_activation_codes_with_amount_and_batch_note(tmp_path: Path) -> None:
    store = PublicBillingStore(tmp_path / "public_activation_codes.db")

    codes = store.create_activation_codes(count=2, amount_cents=550, batch_note="april")

    assert len(codes) == 2
    assert all(len(item["code"]) == 32 for item in codes)


def test_redeem_activation_code_marks_it_used_and_adds_balance(tmp_path: Path) -> None:
    store = PublicBillingStore(tmp_path / "public_activation_codes.db")
    auth_service = PublicAuthService(store)
    user = store.create_user(username="demo", password_hash="hash", signup_bonus_cents=0)
    code = store.create_activation_codes(count=1, amount_cents=550, batch_note="april")[0]["code"]

    redeemed = auth_service.redeem_activation_code(code=code, user_id=user["id"])

    assert redeemed["code"] == code

    with sqlite3.connect(store.db_file) as conn:
        user_row = conn.execute(
            "SELECT balance_cents FROM users WHERE id = ?",
            (int(user["id"]),),
        ).fetchone()
        code_row = conn.execute(
            """
            SELECT status, redeemed_by_user_id, redeemed_at
            FROM activation_codes
            WHERE code = ?
            """,
            (code,),
        ).fetchone()
        ledger_row = conn.execute(
            """
            SELECT scope, user_id, change_cents, balance_after_cents, reason, reference_type, reference_id
            FROM quota_ledger
            ORDER BY id DESC
            LIMIT 1
            """
        ).fetchone()

    assert user_row == (550,)
    assert code_row[0] == "redeemed"
    assert code_row[1] == int(user["id"])
    assert code_row[2] is not None
    assert ledger_row == (
        "user",
        int(user["id"]),
        550,
        550,
        "activation_code_redeem",
        "activation_code",
        code,
    )


def test_redeem_activation_code_cannot_be_reused(tmp_path: Path) -> None:
    store = PublicBillingStore(tmp_path / "public_activation_codes.db")
    auth_service = PublicAuthService(store)
    user = store.create_user(username="demo", password_hash="hash", signup_bonus_cents=0)
    code = store.create_activation_codes(count=1, amount_cents=550, batch_note="april")[0]["code"]

    auth_service.redeem_activation_code(code=code, user_id=user["id"])

    with pytest.raises(ValueError, match="activation code already redeemed"):
        auth_service.redeem_activation_code(code=code, user_id=user["id"])
