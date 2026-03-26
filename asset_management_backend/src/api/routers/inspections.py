"""Inspections router.

MVP endpoints:
- POST /inspections (multipart/form-data, includes photo optional)
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import APIRouter, Depends, File, Form, UploadFile, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from api.db.deps import get_db
from api.db.models import Alert, AlertSeverity, Asset, Inspection, TimelineEvent, TimelineEventType
from api.routers._common import clamp_0_100, not_found
from api.schemas import InspectionCreateMVP, InspectionOutMVP
from api.services import compute_health_score_mvp, ensure_auto_alert_for_asset_mvp
from api.storage import save_inspection_photo_mvp

router = APIRouter(prefix="/inspections", tags=["Inspections"])


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _parse_json_maybe(value: Optional[str]) -> dict[str, Any]:
    if not value:
        return {}
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


@router.post(
    "",
    summary="Log inspection (with optional photo)",
    description=(
        "Log an inspection for an asset. Optionally upload a photo in the same request.\n\n"
        "Send as multipart/form-data:\n"
        "- asset_id (int)\n"
        "- condition_rating (int 1..5)\n"
        "- observations (str, optional)\n"
        "- timestamp (ISO string, optional; defaults to now)\n"
        "- readings (JSON string, optional)\n"
        "- photo (file, optional)\n"
    ),
    response_model=InspectionOutMVP,
    status_code=status.HTTP_201_CREATED,
    operation_id="inspections_create",
)
# PUBLIC_INTERFACE
def create_inspection(
    asset_id: int = Form(..., description="Asset id inspected."),
    condition_rating: int = Form(..., ge=1, le=5, description="Condition rating 1 (bad) .. 5 (excellent)."),
    observations: Optional[str] = Form(None, description="Inspector observations."),
    timestamp: Optional[str] = Form(
        None, description="ISO timestamp for the inspection; defaults to now."
    ),
    readings: Optional[str] = Form(None, description="Optional JSON string of readings/measurements."),
    photo: Optional[UploadFile] = File(None, description="Optional photo upload."),
    db: Session = Depends(get_db),
) -> InspectionOutMVP:
    """Create inspection, save optional photo, compute health score, and auto-generate alert if needed."""
    asset = db.get(Asset, int(asset_id))
    if asset is None:
        raise not_found("Asset")

    occurred_at: datetime
    if timestamp:
        try:
            occurred_at = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
            if occurred_at.tzinfo is None:
                occurred_at = occurred_at.replace(tzinfo=timezone.utc)
        except ValueError:
            occurred_at = _utcnow()
    else:
        occurred_at = _utcnow()

    photo_path: Optional[str] = None
    if photo is not None:
        # Returns relative path under UPLOAD_DIR
        photo_path = save_inspection_photo_mvp(asset_id=asset.id, file=photo)

    create_payload = InspectionCreateMVP(
        asset_id=asset.id,
        condition_rating=int(condition_rating),
        observations=observations,
        photo_path=photo_path,
        timestamp=occurred_at,
        readings=_parse_json_maybe(readings),
    )

    ins = Inspection(
        asset_id=create_payload.asset_id,
        condition_rating=create_payload.condition_rating,
        observations=create_payload.observations,
        photo_path=create_payload.photo_path,
        timestamp=create_payload.timestamp,
        readings=create_payload.readings,
    )
    db.add(ins)
    db.flush()

    # Health score update
    new_score = clamp_0_100(compute_health_score_mvp(asset=asset, latest_condition_rating=ins.condition_rating))
    asset.health_score = new_score

    # Auto-alert if < 40
    alert = ensure_auto_alert_for_asset_mvp(db, asset=asset, health_score=new_score)

    # Timeline
    db.add(
        TimelineEvent(
            asset_id=asset.id,
            event_type=TimelineEventType.INSPECTION_LOGGED,
            description=f"Inspection logged (condition_rating={ins.condition_rating})",
            timestamp=_utcnow(),
            inspection_id=ins.id,
        )
    )
    if alert is not None:
        db.add(
            TimelineEvent(
                asset_id=asset.id,
                event_type=TimelineEventType.ALERT_RAISED,
                description=f"Auto-alert raised: health_score={new_score:.1f}",
                timestamp=_utcnow(),
                alert_id=alert.id,
            )
        )

    db.commit()
    db.refresh(ins)
    db.refresh(asset)

    return InspectionOutMVP.model_validate(ins)
