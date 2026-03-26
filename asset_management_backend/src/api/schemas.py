"""Pydantic schemas for API requests/responses.

The API uses SQLAlchemy ORM models (api.db.models) and exposes typed request/
response models here.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field, ConfigDict

from api.db.models import (
    AlertSeverity,
    AssetCriticality,
    InspectionType,
    TimelineEventType,
    UserRole,
    WorkOrderStatus,
)


class APIMessage(BaseModel):
    """Simple message response."""

    message: str = Field(..., description="Human-readable message.")


# -----------------------
# Auth / Users
# -----------------------
class UserPublic(BaseModel):
    """User data exposed externally."""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(..., description="User id.")
    email: str = Field(..., description="User email address.")
    full_name: Optional[str] = Field(None, description="User full name.")
    role: UserRole = Field(..., description="Role for RBAC.")
    is_active: bool = Field(..., description="Whether the user account is active.")
    created_at: datetime = Field(..., description="Created timestamp.")


class UserCreate(BaseModel):
    """Create user request (admin-only)."""

    email: str = Field(..., description="User email address.")
    full_name: Optional[str] = Field(None, description="User full name.")
    password: str = Field(..., min_length=8, description="User password (min 8 chars).")
    role: UserRole = Field(..., description="Role for RBAC.")


class LoginRequest(BaseModel):
    """Login request payload."""

    email: str = Field(..., description="Email used for login.")
    password: str = Field(..., description="Password used for login.")


class TokenResponse(BaseModel):
    """JWT token response."""

    access_token: str = Field(..., description="JWT access token.")
    token_type: str = Field("bearer", description="Token type (bearer).")
    expires_in: int = Field(..., description="Token expiry in seconds.")
    user: UserPublic = Field(..., description="Current user information.")


# -----------------------
# Assets
# -----------------------
class AssetBase(BaseModel):
    """Common asset fields."""

    asset_tag: str = Field(..., max_length=64, description="Unique asset tag/identifier.")
    name: str = Field(..., max_length=200, description="Asset display name.")
    asset_type: Optional[str] = Field(None, max_length=100, description="Asset type/category.")
    location: Optional[str] = Field(None, max_length=200, description="Physical location/site.")
    description: Optional[str] = Field(None, description="Description/notes.")
    criticality: AssetCriticality = Field(AssetCriticality.MEDIUM, description="Business criticality.")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Arbitrary JSON metadata.")


class AssetCreate(AssetBase):
    """Create asset request."""


class AssetUpdate(BaseModel):
    """Partial asset update request."""

    name: Optional[str] = Field(None, max_length=200, description="Asset display name.")
    asset_type: Optional[str] = Field(None, max_length=100, description="Asset type/category.")
    location: Optional[str] = Field(None, max_length=200, description="Physical location/site.")
    description: Optional[str] = Field(None, description="Description/notes.")
    criticality: Optional[AssetCriticality] = Field(None, description="Business criticality.")
    metadata: Optional[dict[str, Any]] = Field(None, description="Arbitrary JSON metadata.")


class AssetOut(AssetBase):
    """Asset response."""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(..., description="Asset id.")
    health_score: float = Field(..., ge=0, le=100, description="Current health score (0-100).")
    last_inspected_at: Optional[datetime] = Field(None, description="Timestamp of last inspection.")
    created_at: datetime = Field(..., description="Created timestamp.")
    updated_at: datetime = Field(..., description="Updated timestamp.")


# -----------------------
# Inspections / Photos
# -----------------------
class InspectionPhotoOut(BaseModel):
    """Inspection photo metadata."""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(..., description="Photo id.")
    file_key: str = Field(..., description="Storage key/path for photo.")
    original_filename: Optional[str] = Field(None, description="Original filename.")
    content_type: Optional[str] = Field(None, description="MIME content-type.")
    created_at: datetime = Field(..., description="Upload timestamp.")
    url: Optional[str] = Field(None, description="Convenience URL for downloading/previewing.")


class InspectionBase(BaseModel):
    """Common inspection fields."""

    asset_id: int = Field(..., description="Asset id inspected.")
    inspection_type: InspectionType = Field(InspectionType.ROUTINE, description="Inspection type.")
    notes: Optional[str] = Field(None, description="Inspector notes.")
    readings: dict[str, Any] = Field(default_factory=dict, description="Structured readings/measurements.")
    assessed_health_score: Optional[float] = Field(
        None, ge=0, le=100, description="Optional health score assessed during inspection."
    )
    occurred_at: datetime = Field(..., description="When the inspection occurred.")


class InspectionCreate(InspectionBase):
    """Create inspection request."""


class InspectionOut(InspectionBase):
    """Inspection response."""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(..., description="Inspection id.")
    inspector_user_id: Optional[int] = Field(None, description="Inspector user id.")
    created_at: datetime = Field(..., description="Created timestamp.")
    photos: list[InspectionPhotoOut] = Field(default_factory=list, description="Associated photos.")


# -----------------------
# Alerts
# -----------------------
class AlertBase(BaseModel):
    """Common alert fields."""

    asset_id: int = Field(..., description="Asset id.")
    severity: AlertSeverity = Field(AlertSeverity.MEDIUM, description="Alert severity.")
    title: str = Field(..., max_length=200, description="Alert title.")
    description: Optional[str] = Field(None, description="Alert description.")
    is_active: bool = Field(True, description="Whether alert is active.")
    related_work_order_id: Optional[int] = Field(None, description="Work order id related to alert.")


class AlertCreate(AlertBase):
    """Create alert request."""


class AlertUpdate(BaseModel):
    """Update/resolve alert request."""

    severity: Optional[AlertSeverity] = Field(None, description="Alert severity.")
    title: Optional[str] = Field(None, max_length=200, description="Alert title.")
    description: Optional[str] = Field(None, description="Alert description.")
    is_active: Optional[bool] = Field(None, description="Whether alert is active.")
    related_work_order_id: Optional[int] = Field(None, description="Work order id related to alert.")
    resolved_at: Optional[datetime] = Field(None, description="Resolved timestamp.")


class AlertOut(AlertBase):
    """Alert response."""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(..., description="Alert id.")
    created_at: datetime = Field(..., description="Created timestamp.")
    resolved_at: Optional[datetime] = Field(None, description="Resolved timestamp.")


# -----------------------
# Work orders
# -----------------------
class WorkOrderBase(BaseModel):
    """Common work order fields."""

    asset_id: int = Field(..., description="Asset id.")
    title: str = Field(..., max_length=200, description="Work order title.")
    description: Optional[str] = Field(None, description="Work order description.")
    priority: int = Field(3, ge=1, le=5, description="Priority 1 (high) ... 5 (low).")
    status: WorkOrderStatus = Field(WorkOrderStatus.OPEN, description="Work order status.")
    assigned_to_user_id: Optional[int] = Field(None, description="Assigned technician user id.")
    due_date: Optional[datetime] = Field(None, description="Due date.")


class WorkOrderCreate(WorkOrderBase):
    """Create work order request."""


class WorkOrderUpdate(BaseModel):
    """Partial work order update request."""

    title: Optional[str] = Field(None, max_length=200, description="Work order title.")
    description: Optional[str] = Field(None, description="Work order description.")
    priority: Optional[int] = Field(None, ge=1, le=5, description="Priority 1..5.")
    status: Optional[WorkOrderStatus] = Field(None, description="Work order status.")
    assigned_to_user_id: Optional[int] = Field(None, description="Assigned technician user id.")
    due_date: Optional[datetime] = Field(None, description="Due date.")
    completed_at: Optional[datetime] = Field(None, description="Completed timestamp.")


class WorkOrderOut(WorkOrderBase):
    """Work order response."""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(..., description="Work order id.")
    created_by_user_id: Optional[int] = Field(None, description="Creator user id.")
    completed_at: Optional[datetime] = Field(None, description="Completed timestamp.")
    created_at: datetime = Field(..., description="Created timestamp.")
    updated_at: datetime = Field(..., description="Updated timestamp.")


class WorkOrderStatusChange(BaseModel):
    """Change status request (creates audit trail record)."""

    to_status: WorkOrderStatus = Field(..., description="New status.")
    note: Optional[str] = Field(None, description="Optional note describing change.")


# -----------------------
# Timeline / Dashboard
# -----------------------
class TimelineEventOut(BaseModel):
    """Timeline event response."""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(..., description="Event id.")
    asset_id: int = Field(..., description="Asset id.")
    event_type: TimelineEventType = Field(..., description="Event type.")
    inspection_id: Optional[int] = Field(None, description="Inspection id (optional).")
    alert_id: Optional[int] = Field(None, description="Alert id (optional).")
    work_order_id: Optional[int] = Field(None, description="Work order id (optional).")
    title: str = Field(..., description="Event title.")
    message: Optional[str] = Field(None, description="Event message.")
    extra: dict[str, Any] = Field(default_factory=dict, description="Extra JSON payload.")
    created_at: datetime = Field(..., description="Event timestamp.")


class DashboardMetrics(BaseModel):
    """Top-level dashboard KPI response."""

    total_assets: int = Field(..., ge=0, description="Total assets count.")
    avg_health_score: float = Field(..., ge=0, le=100, description="Average health score.")
    assets_at_risk: int = Field(..., ge=0, description="Assets with low health score.")
    open_alerts: int = Field(..., ge=0, description="Count of active alerts.")
    open_work_orders: int = Field(..., ge=0, description="Count of open/in-progress work orders.")


class DashboardOut(BaseModel):
    """Dashboard response containing KPIs and prioritized lists."""

    metrics: DashboardMetrics = Field(..., description="Key performance metrics.")
    top_risk_assets: list[AssetOut] = Field(default_factory=list, description="Assets with lowest health.")
    recent_alerts: list[AlertOut] = Field(default_factory=list, description="Recent active alerts.")
    upcoming_work_orders: list[WorkOrderOut] = Field(
        default_factory=list, description="Work orders prioritized by due date/priority."
    )
