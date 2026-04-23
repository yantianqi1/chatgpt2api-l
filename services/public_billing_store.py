from __future__ import annotations

import secrets
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock

ACTIVATION_CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
ACTIVATION_CODE_LENGTH = 32
MODEL_PRICE_SEEDS = (("gpt-image-1", 100), ("gpt-image-2", 100))
SCHEMA_SQL = (
    "CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT NOT NULL UNIQUE, password_hash TEXT NOT NULL, balance_cents INTEGER NOT NULL CHECK (balance_cents >= 0), status TEXT NOT NULL CHECK (status IN ('active', 'disabled')), created_at TEXT NOT NULL, updated_at TEXT NOT NULL);"
    "CREATE TABLE IF NOT EXISTS user_sessions (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL, token_hash TEXT NOT NULL, expires_at TEXT NOT NULL, created_at TEXT NOT NULL, last_seen_at TEXT NOT NULL, FOREIGN KEY(user_id) REFERENCES users(id));"
    "CREATE INDEX IF NOT EXISTS idx_user_sessions_token_hash ON user_sessions (token_hash);"
    "CREATE TABLE IF NOT EXISTS activation_codes (id INTEGER PRIMARY KEY AUTOINCREMENT, code TEXT NOT NULL UNIQUE, amount_cents INTEGER NOT NULL CHECK (amount_cents >= 0), batch_note TEXT NOT NULL, status TEXT NOT NULL CHECK (status IN ('unused', 'redeemed')), created_at TEXT NOT NULL, redeemed_by_user_id INTEGER, redeemed_at TEXT, FOREIGN KEY(redeemed_by_user_id) REFERENCES users(id));"
    "CREATE TABLE IF NOT EXISTS quota_ledger (id INTEGER PRIMARY KEY AUTOINCREMENT, scope TEXT NOT NULL, user_id INTEGER, change_cents INTEGER NOT NULL, balance_after_cents INTEGER NOT NULL CHECK (balance_after_cents >= 0), reason TEXT NOT NULL, reference_type TEXT NOT NULL, reference_id TEXT NOT NULL, created_at TEXT NOT NULL, FOREIGN KEY(user_id) REFERENCES users(id));"
    "CREATE TABLE IF NOT EXISTS model_pricing (model TEXT PRIMARY KEY, price_cents INTEGER NOT NULL CHECK (price_cents >= 0), enabled INTEGER NOT NULL, updated_at TEXT NOT NULL);"
)


class PublicBillingStore:
    def __init__(self, db_file: Path):
        self.db_file = db_file
        self._lock = Lock()
        self._init_db()

    def list_model_pricing(self) -> list[dict[str, str]]:
        with self._lock, self._connect() as conn:
            rows = conn.execute("SELECT model, price_cents, enabled FROM model_pricing ORDER BY model").fetchall()
        return [self._format_model_pricing(row) for row in rows]

    def update_model_pricing(self, *, model: str, price_cents: int, enabled: bool) -> list[dict[str, str]] | None:
        price_cents = self._require_nonnegative_cents(price_cents, name="price_cents")
        with self._lock, self._connect() as conn:
            if conn.execute(
                "UPDATE model_pricing SET price_cents = ?, enabled = ?, updated_at = ? WHERE model = ?",
                (price_cents, 1 if enabled else 0, self._now(), model),
            ).rowcount == 0:
                return None
        return self.list_model_pricing()

    def create_user(self, *, username: str, password_hash: str, signup_bonus_cents: int) -> dict[str, str]:
        bonus_cents = self._require_nonnegative_cents(signup_bonus_cents, name="signup_bonus_cents")
        now = self._now()
        with self._lock, self._connect() as conn:
            cursor = conn.execute(
                "INSERT INTO users (username, password_hash, balance_cents, status, created_at, updated_at) VALUES (?, ?, ?, 'active', ?, ?)",
                (username, password_hash, bonus_cents, now, now),
            )
            user_id = cursor.lastrowid
            conn.execute(
                "INSERT INTO quota_ledger (scope, user_id, change_cents, balance_after_cents, reason, reference_type, reference_id, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                ("user", user_id, bonus_cents, bonus_cents, "signup_bonus", "user", str(user_id), now),
            )
            row = conn.execute(
                "SELECT id, username, password_hash, balance_cents, status, created_at, updated_at FROM users WHERE id = ?",
                (user_id,),
            ).fetchone()
        return self._format_user(row)

    def get_user_auth_by_username(self, username: str) -> dict[str, str] | None:
        with self._lock, self._connect() as conn:
            row = conn.execute("SELECT id, username, password_hash, balance_cents, status, created_at, updated_at FROM users WHERE username = ?", (username,)).fetchone()
        if row is None:
            return None
        return {"id": str(row["id"]), "username": str(row["username"]), "password_hash": str(row["password_hash"]), "balance": self._format_money(int(row["balance_cents"])), "status": str(row["status"]), "created_at": str(row["created_at"]), "updated_at": str(row["updated_at"])}

    def get_user_by_session_token_hash(self, token_hash: str) -> dict[str, str] | None:
        now = self._now()
        with self._lock, self._connect() as conn:
            row = conn.execute(
                "SELECT u.id, u.username, u.password_hash, u.balance_cents, u.status, u.created_at, u.updated_at FROM user_sessions AS s INNER JOIN users AS u ON u.id = s.user_id WHERE s.token_hash = ? AND s.expires_at > ? ORDER BY s.id DESC LIMIT 1",
                (token_hash, now),
            ).fetchone()
        return self._format_user(row) if row is not None else None

    def delete_session_by_token_hash(self, token_hash: str) -> bool:
        with self._lock, self._connect() as conn:
            cursor = conn.execute("DELETE FROM user_sessions WHERE token_hash = ?", (token_hash,))
        return cursor.rowcount > 0

    def create_session(self, *, user_id: int, token_hash: str, expires_at: str, created_at: str, last_seen_at: str) -> dict[str, str]:
        with self._lock, self._connect() as conn:
            cursor = conn.execute(
                "INSERT INTO user_sessions (user_id, token_hash, expires_at, created_at, last_seen_at) VALUES (?, ?, ?, ?, ?)",
                (user_id, token_hash, expires_at, created_at, last_seen_at),
            )
            row = conn.execute(
                "SELECT id, user_id, token_hash, expires_at, created_at, last_seen_at FROM user_sessions WHERE id = ?",
                (cursor.lastrowid,),
            ).fetchone()
        return self._format_session(row)

    def create_activation_codes(self, *, count: int, amount_cents: int, batch_note: str) -> list[dict[str, object]]:
        code_count = self._require_positive_int(count, name="count")
        prize_cents = self._require_nonnegative_cents(amount_cents, name="amount_cents")
        created_at = self._now()
        rows: list[dict[str, object]] = []
        with self._lock, self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            for _ in range(code_count):
                code = self._generate_activation_code(conn)
                cursor = conn.execute("INSERT INTO activation_codes (code, amount_cents, batch_note, status, created_at) VALUES (?, ?, ?, 'unused', ?)", (code, prize_cents, batch_note, created_at))
                row = conn.execute("SELECT id, code, amount_cents, batch_note, status, created_at, redeemed_by_user_id, redeemed_at FROM activation_codes WHERE id = ?", (cursor.lastrowid,)).fetchone()
                rows.append(self._format_activation_code(row))
        return rows

    def list_activation_codes(
        self,
        *,
        status: str | None = None,
        batch_note: str | None = None,
        redeemed_username: str | None = None,
    ) -> list[dict[str, object]]:
        with self._lock, self._connect() as conn:
            query = ["SELECT ac.id, ac.code, ac.amount_cents, ac.batch_note, ac.status, ac.created_at, ac.redeemed_by_user_id, ac.redeemed_at", "FROM activation_codes AS ac"]
            params: list[object] = []
            if redeemed_username is not None:
                query.append("LEFT JOIN users AS u ON u.id = ac.redeemed_by_user_id")
            conditions = [clause for clause, value in (("ac.status = ?", status), ("ac.batch_note = ?", batch_note), ("u.username = ?", redeemed_username)) if value is not None]
            params.extend([value for value in (status, batch_note, redeemed_username) if value is not None])
            if conditions:
                query.append("WHERE " + " AND ".join(conditions))
            query.append("ORDER BY ac.id DESC")
            rows = conn.execute(" ".join(query), params).fetchall()
        return [self._format_activation_code(row) for row in rows]

    def redeem_activation_code(self, *, code: str, user_id: str) -> dict[str, object]:
        if isinstance(code, bool) or not isinstance(code, str) or not code:
            raise TypeError("code must be a non-empty str")
        user_db_id = self._require_user_id(user_id)
        redeemed_at = self._now()
        with self._lock, self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            code_row = conn.execute(
                """
                SELECT id, code, amount_cents, batch_note, status, created_at
                FROM activation_codes
                WHERE code = ?
                """,
                (code,),
            ).fetchone()
            if code_row is None:
                raise ValueError("activation code not found")
            if str(code_row["status"]) != "unused":
                raise ValueError("activation code already redeemed")
            user_row = conn.execute(
                "SELECT id, balance_cents FROM users WHERE id = ?",
                (user_db_id,),
            ).fetchone()
            if user_row is None:
                raise ValueError("user not found")
            amount_cents = int(code_row["amount_cents"])
            balance_after_cents = int(user_row["balance_cents"]) + amount_cents
            conn.execute(
                """
                UPDATE users
                SET balance_cents = ?, updated_at = ?
                WHERE id = ?
                """,
                (balance_after_cents, redeemed_at, user_db_id),
            )
            conn.execute(
                """
                UPDATE activation_codes
                SET status = 'redeemed', redeemed_by_user_id = ?, redeemed_at = ?
                WHERE id = ?
                """,
                (user_db_id, redeemed_at, int(code_row["id"])),
            )
            conn.execute(
                """
                INSERT INTO quota_ledger (
                    scope, user_id, change_cents, balance_after_cents, reason,
                    reference_type, reference_id, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "user",
                    user_db_id,
                    amount_cents,
                    balance_after_cents,
                    "activation_code_redeem",
                    "activation_code",
                    code,
                    redeemed_at,
                ),
            )
            row = conn.execute(
                """
                SELECT id, code, amount_cents, batch_note, status, created_at,
                       redeemed_by_user_id, redeemed_at
                FROM activation_codes
                WHERE id = ?
                """,
                (int(code_row["id"]),),
            ).fetchone()
        return self._format_activation_code(row)

    def _init_db(self) -> None:
        self.db_file.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            self._create_tables(conn)
            self._seed_model_pricing(conn)

    def _create_tables(self, conn: sqlite3.Connection) -> None:
        conn.executescript(SCHEMA_SQL)

    def _seed_model_pricing(self, conn: sqlite3.Connection) -> None:
        for model, price_cents in MODEL_PRICE_SEEDS:
            conn.execute("INSERT OR IGNORE INTO model_pricing (model, price_cents, enabled, updated_at) VALUES (?, ?, 1, ?)", (model, price_cents, self._now()))

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

    @staticmethod
    def _require_positive_int(value: object, *, name: str) -> int:
        if isinstance(value, bool) or not isinstance(value, int):
            raise TypeError(f"{name} must be an int")
        if value <= 0:
            raise ValueError(f"{name} must be greater than 0")
        return value

    @staticmethod
    def _require_user_id(value: object) -> int:
        if isinstance(value, bool):
            raise TypeError("user_id must be a positive integer string")
        if isinstance(value, int):
            if value <= 0:
                raise ValueError("user_id must be greater than 0")
            return value
        if not isinstance(value, str):
            raise TypeError("user_id must be a positive integer string")
        if not value:
            raise TypeError("user_id must be a positive integer string")
        if not value.isdigit():
            raise ValueError("user_id must be a positive integer string")
        user_id = int(value)
        if user_id <= 0:
            raise ValueError("user_id must be greater than 0")
        return user_id

    def _generate_activation_code(self, conn: sqlite3.Connection) -> str:
        while True:
            code = "".join(secrets.choice(ACTIVATION_CODE_ALPHABET) for _ in range(ACTIVATION_CODE_LENGTH))
            if conn.execute("SELECT 1 FROM activation_codes WHERE code = ?", (code,)).fetchone() is None:
                return code

    def _format_model_pricing(self, row: sqlite3.Row) -> dict[str, str]:
        return {"model": str(row["model"]), "price": self._format_money(int(row["price_cents"])), "enabled": "1" if int(row["enabled"]) else "0"}

    def _format_user(self, row: sqlite3.Row) -> dict[str, str]:
        return {"id": str(row["id"]), "username": str(row["username"]), "balance": self._format_money(int(row["balance_cents"])), "status": str(row["status"]), "created_at": str(row["created_at"]), "updated_at": str(row["updated_at"])}

    @staticmethod
    def _format_session(row: sqlite3.Row) -> dict[str, str]:
        return {"id": str(row["id"]), "user_id": str(row["user_id"]), "expires_at": str(row["expires_at"]), "created_at": str(row["created_at"]), "last_seen_at": str(row["last_seen_at"])}

    def _format_activation_code(self, row: sqlite3.Row) -> dict[str, object]:
        return {"id": str(row["id"]), "code": str(row["code"]), "amount_cents": int(row["amount_cents"]), "batch_note": str(row["batch_note"]), "status": str(row["status"]), "created_at": str(row["created_at"]), "redeemed_by_user_id": None if row["redeemed_by_user_id"] is None else str(row["redeemed_by_user_id"]), "redeemed_at": None if row["redeemed_at"] is None else str(row["redeemed_at"])}
