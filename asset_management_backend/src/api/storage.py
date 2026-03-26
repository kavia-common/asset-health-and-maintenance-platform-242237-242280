"""Local file storage helper for inspection photos.

This implementation stores files on local disk under UPLOAD_DIR.
In production, this can be swapped for object storage (S3, GCS, etc.) while
keeping the DB contract (Inspection.photo_path / InspectionPhoto.file_key).

MVP requirement: Store relative path in Inspection.photo_path and ensure unique filenames.
"""

from __future__ import annotations

import os
import secrets
from pathlib import Path

from fastapi import UploadFile

from api.core.config import get_upload_dir


def _safe_filename(name: str) -> str:
    """Return a basename-only filename to prevent path traversal."""
    return os.path.basename(name or "upload.bin")


def _guess_ext(filename: str) -> str:
    fn = _safe_filename(filename)
    if "." in fn:
        return "." + fn.split(".")[-1].lower()
    return ""


# PUBLIC_INTERFACE
def save_inspection_photo_mvp(*, asset_id: int, file: UploadFile) -> str:
    """Save an uploaded inspection photo to disk and return its relative path.

    Directory structure:
        UPLOAD_DIR/assets/{asset_id}/{random}.{ext}

    Args:
        asset_id: asset id used to group uploads
        file: UploadFile stream

    Returns:
        str: relative path under UPLOAD_DIR suitable for Inspection.photo_path
    """
    upload_root = Path(get_upload_dir())
    target_dir = upload_root / "assets" / str(asset_id)
    target_dir.mkdir(parents=True, exist_ok=True)

    token = secrets.token_urlsafe(16)
    ext = _guess_ext(file.filename or "")
    target_name = f"{token}{ext}"
    target_path = target_dir / target_name

    with target_path.open("wb") as out:
        while True:
            chunk = file.file.read(1024 * 1024)
            if not chunk:
                break
            out.write(chunk)

    return str(target_path.relative_to(upload_root))
