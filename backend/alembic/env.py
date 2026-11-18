"""Alembic environment: uses the app's DATABASE_URL (from .env / environment) and model metadata.

Run from backend/:  alembic upgrade head
"""

from __future__ import annotations

from logging.config import fileConfig

from alembic import context
from sqlalchemy import Connection

from app.models import Base  # noqa: F401  (imports every model onto Base.metadata)

config = context.config
target_metadata = Base.metadata

if config.config_file_name is not None:
    fileConfig(config.config_file_name, disable_existing_loggers=False)


def _configure(**kwargs: object) -> None:
    context.configure(
        target_metadata=target_metadata,
        compare_type=True,  # detect column type changes in autogenerate
        compare_server_default=True,
        **kwargs,
    )


def run_migrations_offline() -> None:
    """Emit SQL to stdout (alembic upgrade head --sql) without connecting."""
    from app.core.config import get_settings

    _configure(
        url=get_settings().database_url.get_secret_value(),
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def _run(connection: Connection) -> None:
    _configure(connection=connection)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    # Tests pass an existing connection; otherwise use the app's engine (same SSL settings).
    connection = config.attributes.get("connection")
    if connection is not None:
        _run(connection)
        return
    from app.database.connection import get_engine

    with get_engine().connect() as connection:
        _run(connection)


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
