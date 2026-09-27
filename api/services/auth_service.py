"""Kasir credential verification and token issuance/rotation/revocation.

Backs routers/kasir.py's POST /kasir/login, /kasir/refresh, /kasir/logout.
"""
import logging
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException
from sqlalchemy.orm import Session

from auth import create_access_token, generate_refresh_token, hash_token, verify_password
from config import config
from models import RefreshToken, User

logger = logging.getLogger(__name__)


def verify_kasir_credentials(db: Session, username: str, password: str) -> User:
    """Look up a Kasir by username and verify the password. Raises 401 on failure."""
    user = db.query(User).filter(User.username == username).first()
    if not user or not verify_password(password, user.password):
        raise HTTPException(status_code=401, detail="Invalid username or password")
    return user


def issue_tokens(db: Session, user: User) -> tuple[str, str]:
    """Issue a fresh access+refresh token pair, persisting the refresh token's hash."""
    access_token = create_access_token(user)

    refresh_token = generate_refresh_token()
    db.add(RefreshToken(
        user_id=user.id,
        token_hash=hash_token(refresh_token),
        expires_at=datetime.now(timezone.utc) + timedelta(days=config.JWT_REFRESH_EXPIRE_DAYS),
    ))
    db.commit()

    return access_token, refresh_token


def _get_live_refresh_token(db: Session, refresh_token: str) -> RefreshToken:
    token_hash = hash_token(refresh_token)
    row = db.query(RefreshToken).filter(RefreshToken.token_hash == token_hash).first()

    now = datetime.now(timezone.utc)
    if not row or row.revoked_at is not None or row.expires_at < now:
        raise HTTPException(status_code=401, detail="Invalid or expired refresh token")

    return row


def refresh_tokens(db: Session, refresh_token: str) -> tuple[str, str]:
    """Rotate a valid refresh token: revoke it and issue a brand-new pair."""
    row = _get_live_refresh_token(db, refresh_token)

    row.revoked_at = datetime.now(timezone.utc)
    db.commit()

    user = db.get(User, row.user_id)
    logger.info("Rotated refresh token for user_id=%s", user.id)

    return issue_tokens(db, user)


def revoke_refresh_token(db: Session, refresh_token: str) -> None:
    """Revoke a refresh token (logout). Idempotent — no error if already revoked/unknown."""
    token_hash = hash_token(refresh_token)
    row = db.query(RefreshToken).filter(RefreshToken.token_hash == token_hash).first()

    if row and row.revoked_at is None:
        row.revoked_at = datetime.now(timezone.utc)
        db.commit()
        logger.info("Revoked refresh token for user_id=%s", row.user_id)
