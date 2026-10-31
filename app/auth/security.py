from datetime import datetime, timedelta, timezone

import jwt
from passlib.context import CryptContext

from app.config import get_settings
from app.models.user import User

_pwd_context = CryptContext(schemes=["bcrypt"])

JWT_ALGORITHM = "HS256"


def hash_password(password: str) -> str:
    return _pwd_context.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    return _pwd_context.verify(password, password_hash)


def _create_token(user: User, token_type: str, expires_delta: timedelta) -> str:
    settings = get_settings()
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user.id),
        "role": user.role,
        "type": token_type,
        "exp": now + expires_delta,
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=JWT_ALGORITHM)


def create_access_token(user: User) -> str:
    settings = get_settings()
    return _create_token(
        user, "access", timedelta(minutes=settings.jwt_access_expire_minutes)
    )


def create_refresh_token(user: User) -> str:
    settings = get_settings()
    return _create_token(
        user, "refresh", timedelta(days=settings.jwt_refresh_expire_days)
    )


def decode_token(token: str) -> dict:
    settings = get_settings()
    return jwt.decode(token, settings.jwt_secret_key, algorithms=[JWT_ALGORITHM])


def create_password_reset_token(user: User) -> str:
    """Single-use, short-lived token for the forgot-password flow.

    Embeds a short slice of the user's current password_hash so the token
    is implicitly invalidated once the password changes (no separate
    used/unused column needed): a token generated before a reset will no
    longer match the hash after that reset succeeds.
    """
    settings = get_settings()
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user.id),
        "type": "password_reset",
        "pwfp": user.password_hash[-12:],
        "exp": now + timedelta(hours=1),
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=JWT_ALGORITHM)


def verify_password_reset_token(token: str, user: User) -> bool:
    try:
        settings = get_settings()
        payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[JWT_ALGORITHM])
    except jwt.InvalidTokenError:
        return False
    if payload.get("type") != "password_reset":
        return False
    if payload.get("sub") != str(user.id):
        return False
    return payload.get("pwfp") == user.password_hash[-12:]
