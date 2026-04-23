from __future__ import annotations

import sqlite3
from pathlib import Path

from services.public_auth_service import PublicAuthService
from services.public_billing_store import PublicBillingStore


def test_hash_and_verify_password(tmp_path: Path) -> None:
    service = PublicAuthService(PublicBillingStore(tmp_path / "public_auth.db"))
    hashed = service.hash_password("secret")

    assert hashed != "secret"
    assert service.verify_password("secret", hashed) is True
    assert service.verify_password("wrong", hashed) is False


def test_session_token_is_not_stored_in_plaintext(tmp_path: Path) -> None:
    store = PublicBillingStore(tmp_path / "public_billing.db")
    service = PublicAuthService(store)
    user = store.create_user(username="demo", password_hash="hash", signup_bonus_cents=0)

    token, session = service.create_session(user["id"])

    assert token
    assert session["token_hash"] != token
    assert "token" not in session

    with sqlite3.connect(store.db_file) as conn:
        row = conn.execute(
            """
            SELECT token_hash
            FROM user_sessions
            WHERE user_id = ?
            ORDER BY id DESC
            LIMIT 1
            """,
            (int(user["id"]),),
        ).fetchone()

    assert row is not None
    assert row[0] == session["token_hash"]
    assert row[0] != token
