from __future__ import annotations

import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone

from services.public_billing_store import PublicBillingStore

PASSWORD_ALGORITHM = "pbkdf2_sha256"
PASSWORD_ITERATIONS = 310_000
PASSWORD_SALT_BYTES = 16
SESSION_TOKEN_BYTES = 32
SESSION_TTL_DAYS = 30


class PublicAuthService:
    def __init__(self, billing_store: PublicBillingStore):
        self._billing_store = billing_store

    def hash_password(self, password: str) -> str:
        salt = secrets.token_bytes(PASSWORD_SALT_BYTES)
        derived = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            salt,
            PASSWORD_ITERATIONS,
        )
        return self._encode_password_hash(salt, derived)

    def verify_password(self, password: str, password_hash: str) -> bool:
        parsed = self._decode_password_hash(password_hash)
        if parsed is None:
            return False
        iterations, salt, expected = parsed
        candidate = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            salt,
            iterations,
        )
        return hmac.compare_digest(candidate, expected)

    def create_session(self, user_id: str) -> tuple[str, dict[str, object]]:
        token = secrets.token_urlsafe(SESSION_TOKEN_BYTES)
        now = datetime.now(timezone.utc)
        token_hash = self._hash_token(token)
        session = self._billing_store.create_session(
            user_id=int(user_id),
            token_hash=token_hash,
            expires_at=self._timestamp(now + timedelta(days=SESSION_TTL_DAYS)),
            created_at=self._timestamp(now),
            last_seen_at=self._timestamp(now),
        )
        return token, session

    @staticmethod
    def _encode_password_hash(salt: bytes, derived: bytes) -> str:
        return f"{PASSWORD_ALGORITHM}${PASSWORD_ITERATIONS}${salt.hex()}${derived.hex()}"

    @staticmethod
    def _decode_password_hash(password_hash: str) -> tuple[int, bytes, bytes] | None:
        parts = str(password_hash or "").split("$")
        if len(parts) != 4 or parts[0] != PASSWORD_ALGORITHM:
            return None
        try:
            iterations = int(parts[1])
            salt = bytes.fromhex(parts[2])
            expected = bytes.fromhex(parts[3])
        except ValueError:
            return None
        if iterations <= 0:
            return None
        return iterations, salt, expected

    @staticmethod
    def _hash_token(token: str) -> str:
        return hashlib.sha256(token.encode("utf-8")).hexdigest()

    @staticmethod
    def _timestamp(value: datetime) -> str:
        return value.isoformat()
