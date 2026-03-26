"""Alerts router.

MVP endpoints:
- GET /alerts -> list alerts (assets with health_score < 40) and/or alert records
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from api.db.deps import get_db
from api.db.models import Alert, Asset
from api.schemas import AlertOutMVP

router = APIRouter(prefix="/alerts", tags=["Alerts"])


@router.get(
    "",
    summary="List alerts",
    description="List alerts. For MVP, this returns active alert records for assets with health_score < 40.",
    response_model=list[AlertOutMVP],
    operation_id="alerts_list",
)
# PUBLIC_INTERFACE
def list_alerts(
    limit: int = Query(100, ge=1, le=200, description="Max items."),
    db: Session = Depends(get_db),
) -> list[AlertOutMVP]:
    """List alerts for red health assets (health_score < 40)."""
    # We only show alerts for assets that are currently in red.
    stmt = (
        select(Alert)
        .join(Asset, Asset.id == Alert.asset_id)
        .where(Asset.health_score < 40)
        .order_by(desc(Alert.created_at))
        .limit(limit)
    )
    alerts = list(db.execute(stmt).scalars().all())
    return [AlertOutMVP.model_validate(a) for a in alerts]
