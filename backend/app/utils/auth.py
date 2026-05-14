"""
Auth Utilities

Password hashing (bcrypt) and JWT issuance / verification helpers used by
the auth service. Kept here so other services can verify tokens without
importing the auth service module.

Configuration:
    JWT_SECRET           - required signing secret for HS256.
    JWT_ALGORITHM        - optional, defaults to 'HS256'.
    JWT_EXPIRES_MINUTES  - optional, defaults to 60.
"""
from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from typing import Any, Dict

import bcrypt
import jwt

from app.utils.logger import AppLogger

logger = AppLogger.get_logger(__file__)


DEFAULT_ALGORITHM = "HS256"
DEFAULT_EXPIRES_MINUTES = 60


def hash_password(plain_password: str) -> str:
    """Hash a plaintext password with bcrypt; returns the encoded hash string."""
    salted = bcrypt.hashpw(plain_password.encode("utf-8"), bcrypt.gensalt())
    return salted.decode("utf-8")


def verify_password(plain_password: str, password_hash: str) -> bool:
    """Constant-time compare a plaintext password against a stored bcrypt hash."""
    try:
        return bcrypt.checkpw(
            plain_password.encode("utf-8"),
            password_hash.encode("utf-8"),
        )
    except Exception as exc:
        logger.error("Password verification failed: %s", exc, exc_info=True)
        return False


def _get_jwt_secret() -> str:
    secret = os.getenv("JWT_SECRET")
    if not secret:
        raise RuntimeError("JWT_SECRET is not set.")
    return secret


def _get_jwt_algorithm() -> str:
    return os.getenv("JWT_ALGORITHM", DEFAULT_ALGORITHM)


def _get_expires_minutes() -> int:
    try:
        return int(os.getenv("JWT_EXPIRES_MINUTES", str(DEFAULT_EXPIRES_MINUTES)))
    except ValueError:
        logger.warning("JWT_EXPIRES_MINUTES is not an int; using default %d", DEFAULT_EXPIRES_MINUTES)
        return DEFAULT_EXPIRES_MINUTES


def create_access_token(*, user_id: int, username: str) -> tuple[str, int]:
    """
    Issue a JWT for the given user.

    Returns:
        (token, expires_in_seconds)
    """
    expires_minutes = _get_expires_minutes()
    now = datetime.now(tz=timezone.utc)
    exp = now + timedelta(minutes=expires_minutes)

    payload: Dict[str, Any] = {
        "sub": str(user_id),
        "username": username,
        "iat": int(now.timestamp()),
        "exp": int(exp.timestamp()),
    }

    token = jwt.encode(payload, _get_jwt_secret(), algorithm=_get_jwt_algorithm())
    return token, expires_minutes * 60


def decode_access_token(token: str) -> Dict[str, Any]:
    """Decode and validate a JWT; raises jwt.PyJWTError on failure."""
    return jwt.decode(
        token,
        _get_jwt_secret(),
        algorithms=[_get_jwt_algorithm()],
    )
