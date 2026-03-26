"""Configuration utilities for the backend.

This module is intentionally small and dependency-free so it can be used by
Alembic and runtime code.
"""

from __future__ import annotations

import os


# PUBLIC_INTERFACE
def get_database_url() -> str:
    """Return the SQLAlchemy-compatible database URL.

    Resolution order:
    1) DATABASE_URL (recommended)
    2) POSTGRES_URL (supported for compatibility with DB visualizer env files)
    3) raise ValueError

    Returns:
        str: Database URL, e.g. "postgresql+psycopg2://user:pass@host:port/db"
    """
    url = os.getenv("DATABASE_URL") or os.getenv("POSTGRES_URL")
    if not url:
        raise ValueError(
            "Database URL not configured. Set DATABASE_URL (preferred) or POSTGRES_URL."
        )

    # Normalize "postgresql://" to SQLAlchemy driver URL if not already specified.
    # This keeps the project flexible while still working out-of-the-box.
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+psycopg2://", 1)

    return url
