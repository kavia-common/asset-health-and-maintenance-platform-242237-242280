"""Security utilities: password hashing, JWT handling, and RBAC dependencies."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from api.core.config import get_access_token_exp_minutes, get_jwt_secret
from api.db.deps import get_db
from api.db.models import User, UserRole

_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
_bearer_scheme = HTTPBearer(auto_error=False)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


# PUBLIC_INTERFACE
def hash_password(password: str) -> str:
    """Hash a password using bcrypt.

    Args:
        password: plaintext password

    Returns:
        Hashed password string.
    """
    return _pwd_context.hash(password)


# PUBLIC_INTERFACE
def verify_password(password: str, password_hash: str) -> bool:
    """Verify a password against a stored hash.

    Args:
        password: plaintext password
        password_hash: stored hash

    Returns:
        True if password matches, else False.
    """
    return _pwd_context.verify(password, password_hash)


# PUBLIC_INTERFACE
def create_access_token(*, subject: str, role: str, user_id: int) -> tuple[str, int]:
    """Create a signed JWT access token.

    Args:
        subject: typically the user email
        role: user role string
        user_id: user id

    Returns:
        (token, expires_in_seconds)
    """
    exp_minutes = get_access_token_exp_minutes()
    expire = _utcnow() + timedelta(minutes=exp_minutes)
    payload = {"sub": subject, "role": role, "uid": user_id, "exp": expire}
    token = jwt.encode(payload, get_jwt_secret(), algorithm="HS256")
    return token, int(exp_minutes * 60)


def _unauthorized(detail: str = "Not authenticated") -> HTTPException:
    return HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=detail)


# PUBLIC_INTERFACE
def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    """FastAPI dependency: parse JWT and load current user from DB.

    Returns:
        User: current authenticated user

    Raises:
        HTTPException(401): if token is missing/invalid or user does not exist/inactive
    """
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise _unauthorized("Missing bearer token")

    token = credentials.credentials
    try:
        payload = jwt.decode(token, get_jwt_secret(), algorithms=["HS256"])
    except jwt.ExpiredSignatureError as exc:
        raise _unauthorized("Token expired") from exc
    except jwt.PyJWTError as exc:
        raise _unauthorized("Invalid token") from exc

    user_id = payload.get("uid")
    if not user_id:
        raise _unauthorized("Invalid token payload")

    user = db.get(User, int(user_id))
    if user is None or not user.is_active:
        raise _unauthorized("User not found or inactive")
    return user


# PUBLIC_INTERFACE
def require_roles(*allowed_roles: UserRole):
    """Factory returning a dependency that enforces allowed roles.

    Usage:
        current_user = Depends(require_roles(UserRole.ADMIN, UserRole.MANAGER))
    """

    def _dep(user: User = Depends(get_current_user)) -> User:
        if user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions for this resource.",
            )
        return user

    return _dep
