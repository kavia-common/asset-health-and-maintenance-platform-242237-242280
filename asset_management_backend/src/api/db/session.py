"""Database session/engine setup."""

from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from api.core.config import get_database_url


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy ORM models."""


# Create engine eagerly so Alembic and runtime can share configuration.
_ENGINE = create_engine(get_database_url(), pool_pre_ping=True)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=_ENGINE)


# PUBLIC_INTERFACE
def get_engine():
    """Return the configured SQLAlchemy engine."""
    return _ENGINE
