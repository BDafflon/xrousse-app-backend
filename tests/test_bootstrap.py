from sqlmodel import select

from app.bootstrap import bootstrap_admin
from app.config import get_settings
from app.models.user import Role, User


def test_bootstrap_creates_admin_when_env_vars_set_and_no_matching_user(
    session, monkeypatch
):
    monkeypatch.setenv("ADMIN_EMAIL", "bootstrap-admin@test.com")
    monkeypatch.setenv("ADMIN_PASSWORD", "bootstrap-secret")
    get_settings.cache_clear()
    try:
        bootstrap_admin(session)

        user = session.exec(
            select(User).where(User.email == "bootstrap-admin@test.com")
        ).first()
        assert user is not None
        assert user.role == Role.admin
    finally:
        get_settings.cache_clear()


def test_bootstrap_is_idempotent_on_second_call(session, monkeypatch):
    monkeypatch.setenv("ADMIN_EMAIL", "bootstrap-admin2@test.com")
    monkeypatch.setenv("ADMIN_PASSWORD", "bootstrap-secret")
    get_settings.cache_clear()
    try:
        bootstrap_admin(session)
        bootstrap_admin(session)

        users = session.exec(
            select(User).where(User.email == "bootstrap-admin2@test.com")
        ).all()
        assert len(users) == 1
    finally:
        get_settings.cache_clear()


def test_bootstrap_noop_when_env_vars_unset(session, monkeypatch):
    monkeypatch.delenv("ADMIN_EMAIL", raising=False)
    monkeypatch.delenv("ADMIN_PASSWORD", raising=False)
    get_settings.cache_clear()
    try:
        bootstrap_admin(session)

        users = session.exec(select(User).where(User.role == Role.admin)).all()
        assert users == []
    finally:
        get_settings.cache_clear()
