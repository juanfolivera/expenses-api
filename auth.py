"""
auth.py
-------
JWT authentication utilities and FastAPI dependency for protected endpoints.

Token strategy:
  - Access token  — short-lived (default 30 min), used on every request.
  - Refresh token — long-lived (default 30 days), used only to obtain a new
                    access token without re-entering credentials.
"""

from datetime import datetime, timedelta, timezone

import bcrypt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt

import config
import database as db

# ── Password hashing ──────────────────────────────────────────────────────────


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode(), hashed.encode())


# ── JWT ───────────────────────────────────────────────────────────────────────

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")

_CREDENTIALS_ERROR = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Invalid or expired token",
    headers={"WWW-Authenticate": "Bearer"},
)


def _create_token(data: dict, expires_delta: timedelta) -> str:
    payload = {**data, "exp": datetime.now(timezone.utc) + expires_delta}
    return jwt.encode(payload, config.JWT_SECRET_KEY, algorithm=config.JWT_ALGORITHM)


def create_access_token(username: str) -> str:
    return _create_token(
        {"sub": username, "type": "access"},
        timedelta(minutes=config.ACCESS_TOKEN_EXPIRE_MINUTES),
    )


def create_refresh_token(username: str) -> str:
    return _create_token(
        {"sub": username, "type": "refresh"},
        timedelta(days=config.REFRESH_TOKEN_EXPIRE_DAYS),
    )


def decode_token(token: str, expected_type: str) -> str:
    """Decodes and validates a JWT. Returns the username or raises 401."""
    try:
        payload = jwt.decode(
            token, config.JWT_SECRET_KEY, algorithms=[config.JWT_ALGORITHM]
        )
    except JWTError:
        raise _CREDENTIALS_ERROR

    if payload.get("type") != expected_type:
        raise _CREDENTIALS_ERROR

    username: str | None = payload.get("sub")
    if not username:
        raise _CREDENTIALS_ERROR

    return username


# ── FastAPI dependency ────────────────────────────────────────────────────────


def get_current_user(token: str = Depends(oauth2_scheme)) -> dict:
    """Dependency that validates the access token and returns the current user."""
    username = decode_token(token, "access")
    user = db.get_user_by_username(username)
    if not user or not user["is_active"]:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user
