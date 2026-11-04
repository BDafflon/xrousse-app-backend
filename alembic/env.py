from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool
from sqlmodel import SQLModel

from app.config import get_settings
from app.db import _normalize_database_url

# --- model imports (append-friendly: each task adds its import here) ---
from app.models.user import User  # noqa: F401
from app.models.tag import Tag  # noqa: F401
from app.models.event import Event, EventTag  # noqa: F401
from app.models.vote import Vote  # noqa: F401
from app.models.subscription import Subscription  # noqa: F401
from app.models.event_share import EventShare  # noqa: F401
from app.models.saved_event import SavedEvent  # noqa: F401
# -------------------------------------------------------------------------

target_metadata = SQLModel.metadata

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

config.set_main_option("sqlalchemy.url", _normalize_database_url(get_settings().database_url))


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
