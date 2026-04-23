from __future__ import annotations

import sqlite3
from pathlib import Path
from threading import Lock
from datetime import datetime, timezone

MODEL_PRICE_SEEDS = (
    ("gpt-image-1", 100),
    ("gpt-image-2", 100),
)

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    balance_cents INTEGER NOT NULL CHECK (balance_cents >= 0),
    status TEXT NOT NULL CHECK (status IN ('active', 'disabled')),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS user_sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    token_hash TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    created_at TEXT NOT NULL,
    last_seen_at TEXT NOT NULL,
    FOREIGN KEY(user_id) REFERENCES users(id)
);

CREATE INDEX IF NOT EXISTS idx_user_sessions_token_hash
ON user_sessions (token_hash);

CREATE TABLE IF NOT EXISTS activation_codes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    code TEXT NOT NULL UNIQUE,
    amount_cents INTEGER NOT NULL CHECK (amount_cents >= 0),
    batch_note TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('unused', 'redeemed')),
    created_at TEXT NOT NULL,
    redeemed_by_user_id INTEGER,
    redeemed_at TEXT,
    FOREIGN KEY(redeemed_by_user_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS quota_ledger (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    scope TEXT NOT NULL,
    user_id INTEGER,
    change_cents INTEGER NOT NULL,
    balance_after_cents INTEGER NOT NULL CHECK (balance_after_cents >= 0),
    reason TEXT NOT NULL,
    reference_type TEXT NOT NULL,
    reference_id TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY(user_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS model_pricing (
    model TEXT PRIMARY KEY,
    price_cents INTEGER NOT NULL CHECK (price_cents >= 0),
    enabled INTEGER NOT NULL,
    updated_at TEXT NOT NULL
);
"""


class PublicBillingStore:
    def __init__(self, db_file: Path):
        self.db_file = db_file
        self._lock = Lock()
        self._init_db()

    def list_model_pricing(self) -> list[dict[str, str]]:
        with self._lock, self._connect() as conn:
            rows = conn.execute(
                "SELECT model, price_cents, enabled FROM model_pricing ORDER BY model"
            ).fetchall()
        return [self._format_model_pricing(row) for row in rows]

    def create_user(
        self,
        *,
        username: str,
        password_hash: str,
        signup_bonus_cents: int,
    ) -> dict[str, str]:
        bonus_cents = self._require_nonnegative_cents(
            signup_bonus_cents,
            name="signup_bonus_cents",
        )
        now = self._now()
        with self._lock, self._connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO users (username, password_hash, balance_cents, status, created_at, updated_at)
                VALUES (?, ?, ?, 'active', ?, ?)
                """,
                (username, password_hash, bonus_cents, now, now),
            )
            user_id = cursor.lastrowid
            conn.execute(
                """
                INSERT INTO quota_ledger (
                    scope, user_id, change_cents, balance_after_cents, reason,
                    reference_type, reference_id, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                ("user", user_id, bonus_cents, bonus_cents, "signup_bonus", "user", str(user_id), now),
            )
            row = conn.execute(
                """
                SELECT id, username, password_hash, balance_cents, status, created_at, updated_at
                FROM users
                WHERE id = ?
                """,
                (user_id,),
        ).fetchone()
        return self._format_user(row)

    def create_session(
        self,
        *,
        user_id: int,
        token_hash: str,
        expires_at: str,
        created_at: str,
        last_seen_at: str,
    ) -> dict[str, str]:
        with self._lock, self._connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO user_sessions (user_id, token_hash, expires_at, created_at, last_seen_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (user_id, token_hash, expires_at, created_at, last_seen_at),
            )
            row = conn.execute(
                """
                SELECT id, user_id, token_hash, expires_at, created_at, last_seen_at
                FROM user_sessions
                WHERE id = ?
                """,
                (cursor.lastrowid,),
            ).fetchone()
        return self._format_session(row)

    def _init_db(self) -> None:
        self.db_file.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            self._create_tables(conn)
            self._seed_model_pricing(conn)

    def _create_tables(self, conn: sqlite3.Connection) -> None:
        conn.executescript(SCHEMA_SQL)

    def _seed_model_pricing(self, conn: sqlite3.Connection) -> None:
        for model, price_cents in MODEL_PRICE_SEEDS:
            conn.execute(
                """
                INSERT OR IGNORE INTO model_pricing (model, price_cents, enabled, updated_at)
                VALUES (?, ?, 1, ?)
                """,
                (model, price_cents, self._now()),
            )

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_file)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()

    @staticmethod
    def _format_money(value_cents: int) -> str:
        cents = abs(int(value_cents))
        sign = "-" if value_cents < 0 else ""
        return f"{sign}{cents // 100}.{cents % 100:02d}"

    @staticmethod
    def _require_nonnegative_cents(value: object, *, name: str) -> int:
        if isinstance(value, bool) or not isinstance(value, int):
            raise TypeError(f"{name} must be an int")
        if value < 0:
            raise ValueError(f"{name} must be greater than or equal to 0")
        return value

    def _format_model_pricing(self, row: sqlite3.Row) -> dict[str, str]:
        return {
            "model": str(row["model"]),
            "price": self._format_money(int(row["price_cents"])),
            "enabled": "1" if int(row["enabled"]) else "0",
        }

    def _format_user(self, row: sqlite3.Row) -> dict[str, str]:
        return {
            "id": str(row["id"]),
            "username": str(row["username"]),
            "balance": self._format_money(int(row["balance_cents"])),
            "status": str(row["status"]),
            "created_at": str(row["created_at"]),
            "updated_at": str(row["updated_at"]),
        }

    @staticmethod
    def _format_session(row: sqlite3.Row) -> dict[str, str]:
        return {
            "id": str(row["id"]),
            "user_id": str(row["user_id"]),
            "expires_at": str(row["expires_at"]),
            "created_at": str(row["created_at"]),
            "last_seen_at": str(row["last_seen_at"]),
        }
