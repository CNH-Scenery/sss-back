"""Dependency-free auth primitives.

Password hashing uses PBKDF2-HMAC and access tokens are HMAC-signed
payloads, so no external crypto libraries are required. The signing key is
read from the ``AUTH_SECRET`` environment variable; set it in production.
"""

import base64
import hashlib
import hmac
import json
import os
import time
from uuid import UUID

_PBKDF2_ALGORITHM = "sha256"
_PBKDF2_ITERATIONS = 200_000
_SALT_BYTES = 16

ACCESS_TOKEN_TTL_SECONDS = 60 * 60 * 24 * 7  # 7 days
_DEFAULT_SECRET = "dev-insecure-secret-change-me"


def _b64encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _b64decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding)


def hash_password(password: str) -> str:
    salt = os.urandom(_SALT_BYTES)
    digest = hashlib.pbkdf2_hmac(
        _PBKDF2_ALGORITHM, password.encode("utf-8"), salt, _PBKDF2_ITERATIONS
    )
    return "$".join(
        [
            f"pbkdf2_{_PBKDF2_ALGORITHM}",
            str(_PBKDF2_ITERATIONS),
            _b64encode(salt),
            _b64encode(digest),
        ]
    )


def verify_password(password: str, stored: str | None) -> bool:
    if not stored:
        return False
    try:
        algorithm_label, iterations_raw, salt_b64, hash_b64 = stored.split("$")
        algorithm = algorithm_label.split("_", 1)[1]
        iterations = int(iterations_raw)
        salt = _b64decode(salt_b64)
        expected = _b64decode(hash_b64)
    except (ValueError, IndexError):
        return False
    candidate = hashlib.pbkdf2_hmac(algorithm, password.encode("utf-8"), salt, iterations)
    return hmac.compare_digest(candidate, expected)


def _secret() -> bytes:
    return os.getenv("AUTH_SECRET", _DEFAULT_SECRET).encode("utf-8")


def _sign(payload_b64: str) -> str:
    signature = hmac.new(_secret(), payload_b64.encode("ascii"), hashlib.sha256).digest()
    return _b64encode(signature)


def create_access_token(user_id: UUID | str, expires_in: int = ACCESS_TOKEN_TTL_SECONDS) -> str:
    payload = {"sub": str(user_id), "exp": int(time.time()) + expires_in}
    payload_b64 = _b64encode(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    return f"{payload_b64}.{_sign(payload_b64)}"


def decode_access_token(token: str | None) -> str | None:
    """Return the subject (user id) for a valid token, otherwise ``None``."""
    if not token:
        return None
    try:
        payload_b64, signature = token.split(".")
    except ValueError:
        return None
    if not hmac.compare_digest(signature, _sign(payload_b64)):
        return None
    try:
        payload = json.loads(_b64decode(payload_b64))
    except (ValueError, json.JSONDecodeError):
        return None
    if int(payload.get("exp", 0)) < int(time.time()):
        return None
    return payload.get("sub")
