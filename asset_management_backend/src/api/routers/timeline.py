"""Timeline router.

MVP endpoint:
- GET /timeline/{asset_id} -> chronological events (inspections, alerts, work orders)
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Path, Query
from sqlalchemy import asc, select
from sqlalchemy.orm import Session

from api.db.deps import get_db
from api.db.models import Asset, TimelineEvent
from api.routers._common import not_found
from api.schemas import TimelineEventOutMVP

router = APIRouter(prefix="/timeline", tags=["Timeline"])


@router.get(
    "/{asset_id}",
    summary="Get asset timeline",
    description="Chronological timeline for an asset.",
    response_model=list[TimelineEventOutMVP],
    operation_id="timeline_get",
)
# PUBLIC_INTERFACE
def get_timeline(
    asset_id: int = Path(..., description="Asset id."),
    limit: int = Query(200, ge=1, le=500, description="Max items."),
    db: Session = Depends(get_db),
) -> list[TimelineEventOutMVP]:
    """Return timeline events for an asset (oldest -> newest)."""
    asset = db.get(Asset, int(asset_id))
    if asset is None:
        raise not_found("Asset")

    stmt = (
        select(TimelineEvent)
        .where(TimelineEvent.asset_id == asset.id)
        .order_by(asc(TimelineEvent.timestamp))
        .limit(limit)
    )
    events = list(db.execute(stmt).scalars().all())
    return [TimelineEventOutMVP.model_validate(e) for e in events]
