"""Work orders router.

MVP endpoints:
- POST /workorders -> create work order for an alert
- PATCH /workorders/{id}/status -> update work order status
"""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Path, status
from sqlalchemy.orm import Session

from api.db.deps import get_db
from api.db.models import Alert, Asset, TimelineEvent, TimelineEventType, WorkOrder, WorkOrderStatus
from api.routers._common import not_found
from api.schemas import WorkOrderCreateFromAlertMVP, WorkOrderOutMVP, WorkOrderStatusPatchMVP

router = APIRouter(prefix="/workorders", tags=["Work Orders"])


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


@router.post(
    "",
    summary="Create work order for an alert",
    description="Create a work order linked to an alert (MVP).",
    response_model=WorkOrderOutMVP,
    status_code=status.HTTP_201_CREATED,
    operation_id="workorders_create",
)
# PUBLIC_INTERFACE
def create_workorder(
    payload: WorkOrderCreateFromAlertMVP, db: Session = Depends(get_db)
) -> WorkOrderOutMVP:
    """Create a work order for an existing alert."""
    alert = db.get(Alert, payload.alert_id)
    if alert is None:
        raise not_found("Alert")

    asset = db.get(Asset, alert.asset_id)
    if asset is None:
        raise not_found("Asset")

    wo = WorkOrder(
        asset_id=asset.id,
        description=payload.description or (alert.description or alert.title),
        status=WorkOrderStatus.OPEN,
        assignee=payload.assignee,
    )
    db.add(wo)
    db.flush()

    alert.related_work_order_id = wo.id

    db.add(
        TimelineEvent(
            asset_id=asset.id,
            event_type=TimelineEventType.WORK_ORDER_CREATED,
            description=f"Work order created (id={wo.id})",
            timestamp=_utcnow(),
            work_order_id=wo.id,
        )
    )

    db.commit()
    db.refresh(wo)
    return WorkOrderOutMVP.model_validate(wo)


@router.patch(
    "/{work_order_id}/status",
    summary="Update work order status",
    description="Update a work order status (MVP).",
    response_model=WorkOrderOutMVP,
    operation_id="workorders_update_status",
)
# PUBLIC_INTERFACE
def patch_workorder_status(
    payload: WorkOrderStatusPatchMVP,
    work_order_id: int = Path(..., description="Work order id."),
    db: Session = Depends(get_db),
) -> WorkOrderOutMVP:
    """Update work order status and add a timeline event."""
    wo = db.get(WorkOrder, int(work_order_id))
    if wo is None:
        raise not_found("WorkOrder")

    try:
        wo.status = WorkOrderStatus(payload.status)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid status") from exc

    wo.updated_at = _utcnow()
    if wo.status == WorkOrderStatus.DONE:
        wo.completed_at = _utcnow()

    db.add(
        TimelineEvent(
            asset_id=wo.asset_id,
            event_type=TimelineEventType.WORK_ORDER_STATUS_CHANGED,
            description=f"Work order status changed to {wo.status.value}",
            timestamp=_utcnow(),
            work_order_id=wo.id,
        )
    )

    db.commit()
    db.refresh(wo)
    return WorkOrderOutMVP.model_validate(wo)
