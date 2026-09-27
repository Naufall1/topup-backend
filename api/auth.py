"""Kasir authentication primitives — password hashing, JWT access tokens, and the
opaque-refresh-token helpers used by services/auth_service.py.

Refresh tokens are deliberately NOT JWTs: they're tracked server-side (stateful,
revocable/rotatable per docs/backend-architecture.md), so a JWT's self-contained
claims would be redundant — an opaque random string is simpler and just as secure.
"""
import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import Annotated

import bcrypt
import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from config import config
from models import User
from session import get_db

bearer_scheme = HTTPBearer()

JWT_ALGORITHM = "HS256"


def verify_password(password: str, hashed: str) -> bool:
    """Check a plaintext password against a bcrypt hash."""
    return bcrypt.checkpw(password.encode(), hashed.encode())


def create_access_token(user: User) -> str:
    """Issue a JWT access token for a Kasir (3h lifetime, see config.JWT_ACCESS_EXPIRE_MINUTES)."""
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user.id),
        "username": user.username,
        "type": "access",
        "iat": now,
        "exp": now + timedelta(minutes=config.JWT_ACCESS_EXPIRE_MINUTES),
    }
    return jwt.encode(payload, config.JWT_SECRET, algorithm=JWT_ALGORITHM)


def decode_access_token(token: str) -> dict:
    """Decode and verify a JWT access token. Raises jwt.PyJWTError on any failure."""
    payload = jwt.decode(token, config.JWT_SECRET, algorithms=[JWT_ALGORITHM])
    if payload.get("type") != "access":
        raise jwt.InvalidTokenError("Not an access token")
    return payload


def generate_refresh_token() -> str:
    """Generate a new opaque refresh token (256 bits of randomness)."""
    return secrets.token_urlsafe(32)


def hash_token(token: str) -> str:
    """SHA-256 hex digest of an opaque token, for DB storage/lookup."""
    return hashlib.sha256(token.encode()).hexdigest()


DBSession = Annotated[Session, Depends(get_db)]
BearerToken = Annotated[HTTPAuthorizationCredentials, Depends(bearer_scheme)]


def get_current_kasir(credentials: BearerToken, db: DBSession) -> User:
    """FastAPI dependency: decode the Authorization: Bearer access token and load the Kasir."""
    try:
        payload = decode_access_token(credentials.credentials)
        user_id = int(payload["sub"])
    except (jwt.PyJWTError, KeyError, ValueError):
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    return user
