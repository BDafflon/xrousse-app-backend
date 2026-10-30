from sqlmodel import Session, create_engine

from app.config import get_settings


def _normalize_database_url(url: str) -> str:
    # Coolify/Postgres providers hand out a bare "postgresql://" URL, which
    # SQLAlchemy resolves to the psycopg (v3) driver by default — this
    # project installs psycopg2-binary instead, so force that driver here.
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+psycopg2://", 1)
    return url


engine = create_engine(_normalize_database_url(get_settings().database_url))


def get_session():
    with Session(engine) as session:
        yield session
