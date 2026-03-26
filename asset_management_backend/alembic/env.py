"""Alembic migration environment.

This file configures Alembic to use the app's SQLAlchemy metadata and reads
the database URL from environment variables.

Env vars:
- DATABASE_URL (preferred)
- POSTGRES_URL (compat)
"""

from __future__ import annotations

from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from api.core.config import get_database_url
from api.db.session import Base

# Import models so they are registered on Base.metadata
from api.db import models  # noqa: F401  # pylint: disable=unused-import

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def _set_sqlalchemy_url() -> None:
    """Set sqlalchemy.url in Alembic config based on environment variable."""
    config.set_main_option("sqlalchemy.url", get_database_url())


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode (no DBAPI engine)."""
    _set_sqlalchemy_url()
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        compare_type=True,
        compare_server_default=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode (with DBAPI engine)."""
    _set_sqlalchemy_url()
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            compare_server_default=True,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
