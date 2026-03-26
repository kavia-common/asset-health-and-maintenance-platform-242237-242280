"""Business logic services for health scoring, alerting, and timeline events."""

from __future__ import annotations

from datetime import datetime, timezone
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
    # Simple deterministic rule set (can evolve later):
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

    Args:
        db: SQLAlchemy session.
        asset_id: asset id.
        event_type: type enum.
        title: short title.
        message: optional message.
        inspection_id/alert_id/work_order_id: optional foreign refs.
        extra: optional JSON payload.

    Returns:
        TimelineEvent persisted entity (pending flush).
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
    """Recompute an asset's health score and create/refresh an auto-alert if needed.

    Rule:
      - If latest inspection has assessed_health_score, use it as health_score.
      - Else, keep current score but still update last_inspected_at.
      - If resulting score <= 70, ensure there is an active auto alert
        (same title prefix) for this asset.
      - If score > 70, resolve any active auto health alerts.

    Args:
        db: SQLAlchemy session.
        asset: Asset ORM object.
        actor: Current user (optional, used for event messages).
        inspection: Optional inspection just created.

    Returns:
        (new_health_score, alert_created_or_updated_or_None)
    """
    new_score = float(asset.health_score or 100.0)

    if inspection is not None:
        asset.last_inspected_at = inspection.occurred_at
        if inspection.assessed_health_score is not None:
            new_score = float(inspection.assessed_health_score)

    # Clamp 0-100
    new_score = max(0.0, min(100.0, new_score))
    asset.health_score = new_score

    created_or_updated_alert: Optional[Alert] = None

    # Find active health alerts (auto generated) for this asset.
    # We mark them by a stable title prefix.
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
            # Update the most recent existing auto alert.
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

        # Timeline entry for alert raised/updated
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
        # Resolve any existing active auto alerts
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
    """Set work order status and create timeline event.

    Args:
        db: SQLAlchemy session
        work_order: work order ORM
        to_status: new status
        actor: current user (optional)
        note: optional change note
    """
    from api.db.models import WorkOrderStatusHistory, TimelineEventType  # local import to avoid cycles

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
def get_recent_timeline_for_asset(db: Session, *, asset_id: int, limit: int = 50) -> list[TimelineEvent]:
    """Return recent timeline events for an asset."""
    q = (
        select(TimelineEvent)
        .where(TimelineEvent.asset_id == asset_id)
        .order_by(desc(TimelineEvent.created_at))
        .limit(max(1, min(200, limit)))
    )
    return list(db.execute(q).scalars().all())
