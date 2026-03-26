"""Database dependencies for FastAPI routes."""

from __future__ import annotations

from collections.abc import Generator

from sqlalchemy.orm import Session

from api.db.session import SessionLocal


# PUBLIC_INTERFACE
def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency that yields a SQLAlchemy session.

    Yields:
        Session: SQLAlchemy session bound to the configured engine.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
