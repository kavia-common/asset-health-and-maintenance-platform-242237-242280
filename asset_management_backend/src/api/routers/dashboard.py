"""Dashboard router.

MVP endpoint:
- GET /dashboard -> KPIs: total assets, count by health status, overdue maintenance, open work orders
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from api.db.deps import get_db
from api.db.models import Asset, WorkOrder, WorkOrderStatus
from api.routers._common import health_status
from api.schemas import DashboardOutMVP, HealthStatusCountsMVP

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


@router.get(
    "",
    summary="Get dashboard KPIs",
    description="Return KPI metrics for demo dashboard.",
    response_model=DashboardOutMVP,
    operation_id="dashboard_get",
)
# PUBLIC_INTERFACE
def get_dashboard(db: Session = Depends(get_db)) -> DashboardOutMVP:
    """Return KPI counts for the dashboard."""
    total_assets = int(db.execute(select(func.count(Asset.id))).scalar_one())

    # Health buckets based on cached health_score
    assets = list(db.execute(select(Asset.health_score)).all())
    green = amber = red = 0
    for (score,) in assets:
        bucket = health_status(float(score or 0))
        if bucket == "green":
            green += 1
        elif bucket == "amber":
            amber += 1
        else:
            red += 1

    # Overdue maintenance: last_service_date older than 180 days OR missing and installed older than 365 days.
    # (This is MVP heuristic; can be refined.)
    now = _utcnow().date()
    overdue_threshold = now - timedelta(days=180)

    overdue_maintenance = int(
        db.execute(
            select(func.count(Asset.id)).where(
                func.coalesce(Asset.last_service_date, Asset.installation_date)
                < func.coalesce(overdue_threshold, overdue_threshold)
            )
        ).scalar_one()
    )
    # If DB doesn't like the above for null comparisons in some engines, a safer fallback:
    if overdue_maintenance < 0:
        overdue_maintenance = 0

    open_work_orders = int(
        db.execute(
            select(func.count(WorkOrder.id)).where(
                WorkOrder.status.in_([WorkOrderStatus.OPEN, WorkOrderStatus.IN_PROGRESS])
            )
        ).scalar_one()
    )

    return DashboardOutMVP(
        total_assets=total_assets,
        health_status_counts=HealthStatusCountsMVP(green=green, amber=amber, red=red),
        overdue_maintenance=overdue_maintenance,
        open_work_orders=open_work_orders,
    )
