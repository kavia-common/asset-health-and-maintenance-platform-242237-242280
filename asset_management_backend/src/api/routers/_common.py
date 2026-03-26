"""Shared router helpers (errors, small mapping utilities)."""

from __future__ import annotations

from typing import Optional

from fastapi import HTTPException, status

from api.db.models import InspectionPhoto


def not_found(entity: str) -> HTTPException:
    """Create a consistent 404 error."""
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND, detail=f"{entity} not found"
    )


def photo_to_url(photo: InspectionPhoto) -> str:
    """Build a stable URL for an uploaded photo."""
    # file_key can contain slashes; route uses :path
    return f"/files/{photo.file_key}"


def health_status(score: float) -> str:
    """Bucket a numeric health score into traffic-light status.

    Returns:
        "green" for >= 70
        "amber" for 40..69
        "red" for < 40
    """
    if score < 40:
        return "red"
    if score < 70:
        return "amber"
    return "green"


def clamp_0_100(value: float) -> float:
    """Clamp a value to [0, 100]."""
    return max(0.0, min(100.0, float(value)))


def opt_str(value: Optional[str]) -> Optional[str]:
    """Normalize empty strings to None."""
    if value is None:
        return None
    v = value.strip()
    return v or None
