"""SQLAlchemy ORM models for the Asset Health & Maintenance app.

NOTE:
- This repository originally scaffolded a richer schema (users/RBAC, inspection photos table, etc.).
- Step 03.01 MVP requirements specify a simplified model set and fields.
- For demo readiness and to match the requirements, we extend existing models with
  MVP-required columns while keeping existing columns for forward compatibility.

If you regenerate Alembic migrations later, these model definitions will be the source of truth.
"""

from __future__ import annotations

import enum
from datetime import date, datetime
from typing import Optional

from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from api.db.session import Base


class UserRole(str, enum.Enum):
    """Application roles for RBAC."""

    ADMIN = "admin"
    MANAGER = "manager"
    TECHNICIAN = "technician"


class AssetCriticality(str, enum.Enum):
    """Asset criticality / business importance."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class InspectionType(str, enum.Enum):
    """Inspection category (richer schema)."""

    ROUTINE = "routine"
    DETAILED = "detailed"
    EMERGENCY = "emergency"


class AlertSeverity(str, enum.Enum):
    """Alert severity level (richer schema)."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class WorkOrderStatus(str, enum.Enum):
    """Work order lifecycle status.

    For MVP, statuses are simplified but compatible with richer flow.
    """

    OPEN = "open"
    IN_PROGRESS = "in_progress"
    DONE = "done"
    CANCELED = "canceled"


class TimelineEventType(str, enum.Enum):
    """Timeline event types for asset history."""

    ASSET_CREATED = "asset_created"
    INSPECTION_LOGGED = "inspection_logged"
    ALERT_RAISED = "alert_raised"
    WORK_ORDER_CREATED = "work_order_created"
    WORK_ORDER_STATUS_CHANGED = "work_order_status_changed"
    NOTE = "note"


class User(Base):
    """User accounts (future auth)."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(320), nullable=False, unique=True, index=True)
    full_name: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)

    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)

    role: Mapped[UserRole] = mapped_column(Enum(UserRole, name="user_role"), nullable=False)

    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    inspections: Mapped[list["Inspection"]] = relationship(back_populates="inspector")
    work_orders_created: Mapped[list["WorkOrder"]] = relationship(
        back_populates="created_by", foreign_keys="WorkOrder.created_by_user_id"
    )
    work_orders_assigned: Mapped[list["WorkOrder"]] = relationship(
        back_populates="assigned_to", foreign_keys="WorkOrder.assigned_to_user_id"
    )


class Asset(Base):
    """Assets being monitored."""

    __tablename__ = "assets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    # Existing fields
    asset_tag: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    asset_type: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    location: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    criticality: Mapped[AssetCriticality] = mapped_column(
        Enum(AssetCriticality, name="asset_criticality"),
        nullable=False,
        server_default=AssetCriticality.MEDIUM.value,
    )

    # MVP-required additional fields
    installation_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    manufacturer: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    last_service_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)

    health_score: Mapped[float] = mapped_column(Float, nullable=False, server_default="100")
    last_inspected_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    metadata: Mapped[dict] = mapped_column(JSON, nullable=False, server_default="{}")

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    inspections: Mapped[list["Inspection"]] = relationship(back_populates="asset")
    alerts: Mapped[list["Alert"]] = relationship(back_populates="asset")
    work_orders: Mapped[list["WorkOrder"]] = relationship(back_populates="asset")
    timeline_events: Mapped[list["TimelineEvent"]] = relationship(back_populates="asset")


class Inspection(Base):
    """Inspection records (MVP + richer fields)."""

    __tablename__ = "inspections"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    asset_id: Mapped[int] = mapped_column(
        ForeignKey("assets.id", ondelete="CASCADE"), nullable=False, index=True
    )
    inspector_user_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )

    # Richer inspection type remains
    inspection_type: Mapped[InspectionType] = mapped_column(
        Enum(InspectionType, name="inspection_type"),
        nullable=False,
        server_default=InspectionType.ROUTINE.value,
    )

    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    readings: Mapped[dict] = mapped_column(JSON, nullable=False, server_default="{}")
    assessed_health_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    # MVP-required fields
    condition_rating: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    observations: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    photo_path: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    timestamp: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    asset: Mapped["Asset"] = relationship(back_populates="inspections")
    inspector: Mapped[Optional["User"]] = relationship(back_populates="inspections")
    photos: Mapped[list["InspectionPhoto"]] = relationship(back_populates="inspection")


class InspectionPhoto(Base):
    """Photo references for inspections (richer schema table)."""

    __tablename__ = "inspection_photos"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    inspection_id: Mapped[int] = mapped_column(
        ForeignKey("inspections.id", ondelete="CASCADE"), nullable=False, index=True
    )

    file_key: Mapped[str] = mapped_column(String(512), nullable=False, unique=True)
    original_filename: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    content_type: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    inspection: Mapped["Inspection"] = relationship(back_populates="photos")


class Alert(Base):
    """Alerts raised for at-risk assets."""

    __tablename__ = "alerts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    asset_id: Mapped[int] = mapped_column(
        ForeignKey("assets.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # Richer fields
    severity: Mapped[AlertSeverity] = mapped_column(
        Enum(AlertSeverity, name="alert_severity"),
        nullable=False,
        server_default=AlertSeverity.MEDIUM.value,
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False, default="Alert")
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")

    # MVP-required fields
    type: Mapped[str] = mapped_column(String(100), nullable=False, server_default="health_score")
    priority: Mapped[str] = mapped_column(String(50), nullable=False, server_default="medium")

    related_work_order_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("work_orders.id", ondelete="SET NULL"), nullable=True, index=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    asset: Mapped["Asset"] = relationship(back_populates="alerts")
    related_work_order: Mapped[Optional["WorkOrder"]] = relationship(back_populates="alerts")


class WorkOrder(Base):
    """Work orders created for maintenance actions (MVP + richer fields)."""

    __tablename__ = "work_orders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    asset_id: Mapped[int] = mapped_column(
        ForeignKey("assets.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # Richer fields
    title: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    priority: Mapped[int] = mapped_column(Integer, nullable=False, server_default="3")
    status: Mapped[WorkOrderStatus] = mapped_column(
        Enum(WorkOrderStatus, name="work_order_status"),
        nullable=False,
        server_default=WorkOrderStatus.OPEN.value,
        index=True,
    )
    created_by_user_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    assigned_to_user_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    due_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # MVP-required fields
    description: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    assignee: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    asset: Mapped["Asset"] = relationship(back_populates="work_orders")
    created_by: Mapped[Optional["User"]] = relationship(
        back_populates="work_orders_created", foreign_keys=[created_by_user_id]
    )
    assigned_to: Mapped[Optional["User"]] = relationship(
        back_populates="work_orders_assigned", foreign_keys=[assigned_to_user_id]
    )

    alerts: Mapped[list["Alert"]] = relationship(back_populates="related_work_order")
    status_history: Mapped[list["WorkOrderStatusHistory"]] = relationship(back_populates="work_order")


class WorkOrderStatusHistory(Base):
    """Status history audit trail for work orders (richer schema)."""

    __tablename__ = "work_order_status_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    work_order_id: Mapped[int] = mapped_column(
        ForeignKey("work_orders.id", ondelete="CASCADE"), nullable=False, index=True
    )

    from_status: Mapped[Optional[WorkOrderStatus]] = mapped_column(
        Enum(WorkOrderStatus, name="work_order_status"),
        nullable=True,
    )
    to_status: Mapped[WorkOrderStatus] = mapped_column(
        Enum(WorkOrderStatus, name="work_order_status"),
        nullable=False,
    )

    changed_by_user_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    changed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    work_order: Mapped["WorkOrder"] = relationship(back_populates="status_history")
    changed_by: Mapped[Optional["User"]] = relationship()


class TimelineEvent(Base):
    """Generic event stream for asset history timeline.

    Supports:
    - richer schema (title/message/extra/created_at)
    - MVP schema (description/timestamp)
    """

    __tablename__ = "timeline_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    asset_id: Mapped[int] = mapped_column(
        ForeignKey("assets.id", ondelete="CASCADE"), nullable=False, index=True
    )

    event_type: Mapped[TimelineEventType] = mapped_column(
        Enum(TimelineEventType, name="timeline_event_type"),
        nullable=False,
        index=True,
    )

    inspection_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("inspections.id", ondelete="SET NULL"), nullable=True, index=True
    )
    alert_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("alerts.id", ondelete="SET NULL"), nullable=True, index=True
    )
    work_order_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("work_orders.id", ondelete="SET NULL"), nullable=True, index=True
    )

    # Richer fields
    title: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    extra: Mapped[dict] = mapped_column(JSON, nullable=False, server_default="{}")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), index=True
    )

    # MVP-required fields
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    timestamp: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    asset: Mapped["Asset"] = relationship(back_populates="timeline_events")


Index("ix_assets_type_location", Asset.asset_type, Asset.location)
Index("ix_inspections_asset_occurred_at", Inspection.asset_id, Inspection.occurred_at)
UniqueConstraint("inspection_id", "file_key", name="uq_inspection_photo_inspection_file_key")
