from datetime import datetime, timedelta, timezone

import jwt
import pytest
from fastapi import HTTPException

from app.auth.dependencies import get_current_user, require_role
from app.auth.security import JWT_ALGORITHM, create_access_token, create_refresh_token
from app.config import get_settings
from app.models.user import Role, User


def _make_user(session, role: Role = Role.lecteur) -> User:
    user = User(email="dep@test.com", password_hash="irrelevant", role=role)
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


def test_get_current_user_rejects_malformed_token(session):
    with pytest.raises(HTTPException) as exc_info:
        get_current_user(token="not-a-real-token", session=session)
    assert exc_info.value.status_code == 401


def test_get_current_user_rejects_expired_token(session):
    user = _make_user(session)
    settings = get_settings()
    payload = {
        "sub": str(user.id),
        "role": user.role,
        "type": "access",
        "exp": datetime.now(timezone.utc) - timedelta(minutes=5),
    }
    expired_token = jwt.encode(
        payload, settings.jwt_secret_key, algorithm=JWT_ALGORITHM
    )

    with pytest.raises(HTTPException) as exc_info:
        get_current_user(token=expired_token, session=session)
    assert exc_info.value.status_code == 401


def test_get_current_user_rejects_refresh_token_as_access(session):
    user = _make_user(session)
    refresh_token = create_refresh_token(user)

    with pytest.raises(HTTPException) as exc_info:
        get_current_user(token=refresh_token, session=session)
    assert exc_info.value.status_code == 401


def test_get_current_user_rejects_unknown_user_id(session):
    settings = get_settings()
    payload = {
        "sub": "999999",
        "role": Role.lecteur,
        "type": "access",
        "exp": datetime.now(timezone.utc) + timedelta(minutes=5),
    }
    token = jwt.encode(payload, settings.jwt_secret_key, algorithm=JWT_ALGORITHM)

    with pytest.raises(HTTPException) as exc_info:
        get_current_user(token=token, session=session)
    assert exc_info.value.status_code == 401


def test_get_current_user_accepts_valid_access_token(session):
    user = _make_user(session)
    access_token = create_access_token(user)

    result = get_current_user(token=access_token, session=session)
    assert result.id == user.id
    assert result.email == user.email


def test_require_role_rejects_mismatched_role(session):
    user = _make_user(session, role=Role.lecteur)
    dependency = require_role(Role.admin)

    with pytest.raises(HTTPException) as exc_info:
        dependency(current_user=user)
    assert exc_info.value.status_code == 403


def test_require_role_accepts_matching_role(session):
    user = _make_user(session, role=Role.admin)
    dependency = require_role(Role.admin)

    result = dependency(current_user=user)
    assert result is user
