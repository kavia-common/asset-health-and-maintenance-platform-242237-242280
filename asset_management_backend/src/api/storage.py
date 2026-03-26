"""Local file storage helper for inspection photos.

This implementation stores files on local disk under UPLOAD_DIR.
In production, this can be swapped for object storage (S3, GCS, etc.) while
keeping the DB contract (InspectionPhoto.file_key).
"""

from __future__ import annotations

import os
import secrets
from pathlib import Path
from typing import Tuple

from fastapi import UploadFile

from api.core.config import get_upload_dir


def _safe_filename(name: str) -> str:
    # Keep only basename to avoid path traversal; additional sanitization can be added.
    return os.path.basename(name or "upload.bin")


# PUBLIC_INTERFACE
def save_inspection_photo(*, inspection_id: int, file: UploadFile) -> Tuple[str, str | None]:
    """Save an uploaded photo to disk and return (file_key, content_type).

    Args:
        inspection_id: inspection id for folder grouping.
        file: UploadFile (streamed by FastAPI).

    Returns:
        (file_key, content_type)
        file_key is a relative path under UPLOAD_DIR.
    """
    upload_root = Path(get_upload_dir())
    target_dir = upload_root / "inspections" / str(inspection_id)
    target_dir.mkdir(parents=True, exist_ok=True)

    ext = ""
    original = _safe_filename(file.filename or "")
    if "." in original:
        ext = "." + original.split(".")[-1].lower()

    token = secrets.token_urlsafe(16)
    target_name = f"{token}{ext}"
    target_path = target_dir / target_name

    with target_path.open("wb") as out:
        # UploadFile exposes a file-like object
        while True:
            chunk = file.file.read(1024 * 1024)
            if not chunk:
                break
            out.write(chunk)

    file_key = str(target_path.relative_to(upload_root))
    return file_key, file.content_type
