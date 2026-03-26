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


# PUBLIC_INTERFACE
def get_jwt_secret() -> str:
    """Return the JWT signing secret.

    Env vars:
        - JWT_SECRET (required)

    Returns:
        str: secret used for signing/verifying JWTs.
    """
    secret = os.getenv("JWT_SECRET")
    if not secret:
        raise ValueError("JWT secret not configured. Set JWT_SECRET.")
    return secret


# PUBLIC_INTERFACE
def get_access_token_exp_minutes() -> int:
    """Return access token expiry duration in minutes.

    Env vars:
        - ACCESS_TOKEN_EXPIRE_MINUTES (optional, default 60)

    Returns:
        int: token expiry in minutes
    """
    raw = os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "60").strip()
    try:
        value = int(raw)
    except ValueError as exc:
        raise ValueError("ACCESS_TOKEN_EXPIRE_MINUTES must be an integer.") from exc
    return max(5, value)


# PUBLIC_INTERFACE
def get_upload_dir() -> str:
    """Return directory for storing uploaded inspection photos.

    Env vars:
        - UPLOAD_DIR (optional, default './uploads')

    Returns:
        str: filesystem path (relative or absolute) for uploads directory.
    """
    return os.getenv("UPLOAD_DIR", "./uploads")
