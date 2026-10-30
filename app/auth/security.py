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
