"""Business logic services for health scoring, alerting, and timeline events.

This module contains:
- Existing richer (future) logic helpers for timeline and work orders.
- MVP-required health score calculation (age + days since service + condition rating).
- MVP-required auto-alert generation when health_score < 40.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Optional

from sqlalchemy import and_, desc, select
from sqlalchemy.orm import Session

from api.db.models import (
    Alert,
    AlertSeverity,
    Asset,
    Inspection,
    TimelineEvent,
    TimelineEventType,
    User,
    WorkOrder,
    WorkOrderStatus,
)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _severity_for_health(score: float) -> AlertSeverity:
    if score <= 30:
        return AlertSeverity.CRITICAL
    if score <= 50:
        return AlertSeverity.HIGH
    if score <= 70:
        return AlertSeverity.MEDIUM
    return AlertSeverity.LOW


def _title_for_health(score: float) -> str:
    if score <= 30:
        return "Asset health critical"
    if score <= 50:
        return "Asset health high risk"
    if score <= 70:
        return "Asset health degraded"
    return "Asset health warning"


# PUBLIC_INTERFACE
def compute_health_score_mvp(*, asset: Asset, latest_condition_rating: int) -> float:
    """Compute a demo-ready health score (0-100).

    Requirements (MVP):
      - Use age, days since last service, and latest inspection condition_rating.

    Heuristic implementation:
      - Base score from condition_rating:
            rating 5 -> 90
            rating 4 -> 75
            rating 3 -> 60
            rating 2 -> 35
            rating 1 -> 15
      - Age penalty: -1 per year since installation (capped at 25)
      - Service penalty: - (days_since_service / 30) (capped at 25)
      - If last_service_date is missing, treat it as installation_date for penalty.
      - Clamp to [0, 100]

    Args:
        asset: Asset ORM entity
        latest_condition_rating: 1..5

    Returns:
        float: health score 0..100
    """
    rating = int(max(1, min(5, latest_condition_rating)))
    rating_base = {5: 90.0, 4: 75.0, 3: 60.0, 2: 35.0, 1: 15.0}[rating]

    today = date.today()

    install = getattr(asset, "installation_date", None)
    last_service = getattr(asset, "last_service_date", None) or install

    age_penalty = 0.0
    if install:
        years = max(0.0, (today - install).days / 365.25)
        age_penalty = min(25.0, years * 1.0)

    service_penalty = 0.0
    if last_service:
        months = max(0.0, (today - last_service).days / 30.0)
        service_penalty = min(25.0, months * 1.0)

    score = rating_base - age_penalty - service_penalty
    return max(0.0, min(100.0, float(score)))


# PUBLIC_INTERFACE
def ensure_auto_alert_for_asset_mvp(
    db: Session, *, asset: Asset, health_score: float
) -> Optional[Alert]:
    """Ensure an auto-generated alert exists when asset health is red (< 40).

    Requirements:
      - Generate Alert automatically if health_score < 40

    Strategy:
      - If health_score < 40: create an active alert if no active auto-alert exists.
      - If health_score >= 40: do nothing (MVP requirement doesn't mention auto-resolve).
    """
    score = float(health_score)
    if score >= 40.0:
        return None

    title_prefix = "Auto:"
    existing = (
        db.execute(
            select(Alert).where(
                and_(
                    Alert.asset_id == asset.id,
                    Alert.is_active.is_(True),
                    Alert.title.like(f"{title_prefix}%"),
                )
            )
        )
        .scalars()
        .first()
    )
    if existing:
        # Refresh details for demo clarity
        existing.priority = "high"
        existing.type = "health_score"
        existing.title = f"{title_prefix} Asset health red"
        existing.description = f"Health score is {score:.1f}/100 (< 40)."
        return existing

    alert = Alert(
        asset_id=asset.id,
        type="health_score",
        priority="high",
        title=f"{title_prefix} Asset health red",
        description=f"Health score is {score:.1f}/100 (< 40).",
        is_active=True,
        severity=AlertSeverity.HIGH,
    )
    db.add(alert)
    db.flush()
    return alert


# PUBLIC_INTERFACE
def create_timeline_event(
    db: Session,
    *,
    asset_id: int,
    event_type: TimelineEventType,
    title: str,
    message: Optional[str] = None,
    inspection_id: Optional[int] = None,
    alert_id: Optional[int] = None,
    work_order_id: Optional[int] = None,
    extra: Optional[dict] = None,
) -> TimelineEvent:
    """Create and persist a timeline event for an asset.

    NOTE: This is the richer (non-MVP) event schema using title/message/extra.
    The MVP requirement uses a simpler TimelineEvent.description/timestamp model.
    Both can co-exist because the DB schema in this repo already supports richer events.
    """
    ev = TimelineEvent(
        asset_id=asset_id,
        event_type=event_type,
        inspection_id=inspection_id,
        alert_id=alert_id,
        work_order_id=work_order_id,
        title=title,
        message=message,
        extra=extra or {},
    )
    db.add(ev)
    return ev


# PUBLIC_INTERFACE
def recompute_asset_health_and_maybe_alert(
    db: Session,
    *,
    asset: Asset,
    actor: Optional[User],
    inspection: Optional[Inspection] = None,
) -> tuple[float, Optional[Alert]]:
    """Existing richer health-score recomputation (kept for forward compatibility)."""
    new_score = float(asset.health_score or 100.0)

    if inspection is not None:
        asset.last_inspected_at = inspection.occurred_at
        if inspection.assessed_health_score is not None:
            new_score = float(inspection.assessed_health_score)

    new_score = max(0.0, min(100.0, new_score))
    asset.health_score = new_score

    created_or_updated_alert: Optional[Alert] = None

    title_prefix = "Auto:"
    q = select(Alert).where(
        and_(
            Alert.asset_id == asset.id,
            Alert.is_active.is_(True),
            Alert.title.like(f"{title_prefix}%"),
        )
    )
    active_auto_alerts = list(db.execute(q).scalars().all())

    if new_score <= 70:
        severity = _severity_for_health(new_score)
        title = f"{title_prefix} {_title_for_health(new_score)}"
        desc = (
            f"Auto-generated alert: asset health score is {new_score:.1f}/100."
            + (f" Latest inspection id: {inspection.id}." if inspection else "")
        )

        if active_auto_alerts:
            alert = active_auto_alerts[0]
            alert.severity = severity
            alert.title = title
            alert.description = desc
            created_or_updated_alert = alert
        else:
            alert = Alert(
                asset_id=asset.id,
                severity=severity,
                title=title,
                description=desc,
                is_active=True,
            )
            db.add(alert)
            created_or_updated_alert = alert

        create_timeline_event(
            db,
            asset_id=asset.id,
            event_type=TimelineEventType.ALERT_RAISED,
            title="Alert raised",
            message=title,
            alert_id=created_or_updated_alert.id if created_or_updated_alert.id else None,
            extra={"health_score": new_score, "severity": severity.value},
        )
    else:
        now = _utcnow()
        for alert in active_auto_alerts:
            alert.is_active = False
            alert.resolved_at = now

    return new_score, created_or_updated_alert


# PUBLIC_INTERFACE
def set_work_order_status(
    db: Session,
    *,
    work_order: WorkOrder,
    to_status: WorkOrderStatus,
    actor: Optional[User],
    note: Optional[str],
) -> None:
    """Existing richer work-order status logic (kept for forward compatibility)."""
    from api.db.models import WorkOrderStatusHistory  # local import to avoid cycles

    if work_order.status == to_status:
        return

    hist = WorkOrderStatusHistory(
        work_order_id=work_order.id,
        from_status=work_order.status,
        to_status=to_status,
        changed_by_user_id=actor.id if actor else None,
        note=note,
    )
    work_order.status = to_status
    if to_status == WorkOrderStatus.DONE:
        work_order.completed_at = _utcnow()
    db.add(hist)

    create_timeline_event(
        db,
        asset_id=work_order.asset_id,
        event_type=TimelineEventType.WORK_ORDER_STATUS_CHANGED,
        title="Work order status changed",
        message=f"{hist.from_status.value if hist.from_status else None} → {to_status.value}",
        work_order_id=work_order.id,
        extra={"note": note, "changed_by_user_id": actor.id if actor else None},
    )


# PUBLIC_INTERFACE
def get_recent_timeline_for_asset(
    db: Session, *, asset_id: int, limit: int = 50
) -> list[TimelineEvent]:
    """Return recent timeline events for an asset."""
    q = (
        select(TimelineEvent)
        .where(TimelineEvent.asset_id == asset_id)
        .order_by(desc(TimelineEvent.created_at))
        .limit(max(1, min(200, limit)))
    )
    return list(db.execute(q).scalars().all())
