import os

os.environ.setdefault("DATABASE_URL", "sqlite://")
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-at-least-32-bytes-long")
os.environ.setdefault("RESEND_API_KEY", "test-resend-key")
os.environ.setdefault("RESEND_FROM_EMAIL", "test@example.com")

import pytest
from sqlmodel import SQLModel, Session, create_engine
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient

from app.main import app
from app.db import get_session
from app.seed_tags import seed as seed_tags


@pytest.fixture(name="session")
def session_fixture():
    test_engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(test_engine)
    with Session(test_engine) as session:
        seed_tags(session)
        yield session
    SQLModel.metadata.drop_all(test_engine)


@pytest.fixture(name="client")
def client_fixture(session):
    def get_session_override():
        return session

    app.dependency_overrides[get_session] = get_session_override

    with TestClient(app) as client:
        yield client

    app.dependency_overrides.clear()


@pytest.fixture(name="redacteur_token")
def redacteur_token_fixture(session):
    from app.auth.security import create_access_token
    from app.models.user import Role, User

    user = User(
        email="redacteur@test.com",
        password_hash="irrelevant",
        role=Role.redacteur,
    )
    session.add(user)
    session.commit()
    session.refresh(user)

    return create_access_token(user)


@pytest.fixture(name="lecteur_token")
def lecteur_token_fixture(session):
    from app.auth.security import create_access_token
    from app.models.user import Role, User

    user = User(
        email="lecteur@test.com",
        password_hash="irrelevant",
        role=Role.lecteur,
    )
    session.add(user)
    session.commit()
    session.refresh(user)

    return create_access_token(user)


@pytest.fixture(name="admin_user_id")
def admin_user_id_fixture(session):
    from app.models.user import Role, User

    user = User(
        email="admin@test.com",
        password_hash="irrelevant",
        role=Role.admin,
    )
    session.add(user)
    session.commit()
    session.refresh(user)

    return user.id


@pytest.fixture(name="admin_token")
def admin_token_fixture(session, admin_user_id):
    from app.auth.security import create_access_token
    from app.models.user import User

    user = session.get(User, admin_user_id)
    return create_access_token(user)


@pytest.fixture(name="other_lecteur_token")
def other_lecteur_token_fixture(session):
    from app.auth.security import create_access_token
    from app.models.user import Role, User

    user = User(
        email="other-lecteur@test.com",
        password_hash="irrelevant",
        role=Role.lecteur,
    )
    session.add(user)
    session.commit()
    session.refresh(user)

    return create_access_token(user)


@pytest.fixture(name="tag_id")
def tag_id_fixture(session):
    from sqlmodel import select

    from app.models.tag import Tag

    tag = session.exec(select(Tag)).first()
    return tag.id
