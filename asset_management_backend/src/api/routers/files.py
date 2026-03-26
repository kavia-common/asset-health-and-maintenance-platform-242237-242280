"""Files router.

Serves inspection photos stored under UPLOAD_DIR.

MVP endpoint:
- GET /files/{photo_path:path}
"""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from api.core.config import get_upload_dir
from api.db.deps import get_db
from api.db.models import Inspection
from api.routers._common import not_found

router = APIRouter(prefix="/files", tags=["Files"])


@router.get(
    "/{photo_path:path}",
    summary="Serve uploaded inspection photo",
    description="Serve a photo by its stored relative path (photo_path).",
    operation_id="files_get",
)
# PUBLIC_INTERFACE
def serve_photo(photo_path: str, db: Session = Depends(get_db)):
    """Serve a stored photo if it is referenced by an inspection record."""
    # Authorization-by-reference: only serve files that are referenced in DB.
    ref = (
        db.execute(select(Inspection).where(Inspection.photo_path == photo_path))
        .scalars()
        .first()
    )
    if ref is None:
        raise not_found("File")

    root = Path(get_upload_dir()).resolve()
    path = (root / photo_path).resolve()
    if not str(path).startswith(str(root)):
        raise HTTPException(status_code=400, detail="Invalid photo path")

    if not path.exists():
        raise not_found("File")

    return FileResponse(str(path))
