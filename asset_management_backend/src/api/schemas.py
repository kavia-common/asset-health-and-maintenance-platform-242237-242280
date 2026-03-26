"""Pydantic schemas for API requests/responses.

This codebase contains:
1) Existing richer schemas (auth/RBAC, assets with tags, inspection photos, etc.)
2) MVP schemas required by Step 03.01 attachment (source of truth)

We keep both sets to avoid breaking future steps; routers for MVP use the *MVP
classes* below.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field

from api.db.models import (
    AlertSeverity,
    AssetCriticality,
    InspectionType,
    TimelineEventType,
    UserRole,
    WorkOrderStatus,
)

# -----------------------
# Generic
# -----------------------


class APIMessage(BaseModel):
    """Simple message response."""

    message: str = Field(..., description="Human-readable message.")


# ============================================================================
# MVP SCHEMAS (Step 03.01 requirements)
# ============================================================================


class AssetCreateMVP(BaseModel):
    """MVP: Create asset request."""

    asset_tag: str = Field(..., max_length=64, description="Unique asset identifier/tag.")
    name: str = Field(..., max_length=200, description="Asset name.")
    asset_type: Optional[str] = Field(None, max_length=100, description="Type/category.")
    location: Optional[str] = Field(None, max_length=200, description="Location/site.")
    installation_date: Optional[date] = Field(None, description="Date installed.")
    manufacturer: Optional[str] = Field(None, max_length=200, description="Manufacturer name.")
    last_service_date: Optional[date] = Field(None, description="Last serviced date.")
    health_score: Optional[float] = Field(
        None, ge=0, le=100, description="Optional initial health score (defaults to 100)."
    )


class AssetOutMVP(BaseModel):
    """MVP: Asset response."""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(..., description="Asset id.")
    asset_tag: str = Field(..., description="Asset identifier/tag.")
    name: str = Field(..., description="Asset name.")
    asset_type: Optional[str] = Field(None, description="Type/category.")
    location: Optional[str] = Field(None, description="Location/site.")
    installation_date: Optional[date] = Field(None, description="Date installed.")
    manufacturer: Optional[str] = Field(None, description="Manufacturer name.")
    last_service_date: Optional[date] = Field(None, description="Last serviced date.")
    health_score: float = Field(..., ge=0, le=100, description="Computed health score.")


class InspectionCreateMVP(BaseModel):
    """MVP: Create inspection request (internal use; router uses multipart form)."""

    asset_id: int = Field(..., description="Asset id inspected.")
    condition_rating: int = Field(..., ge=1, le=5, description="Condition rating 1..5.")
    observations: Optional[str] = Field(None, description="Inspector observations.")
    photo_path: Optional[str] = Field(None, description="Relative photo path under UPLOAD_DIR.")
    timestamp: datetime = Field(..., description="Inspection timestamp.")
    readings: dict[str, Any] = Field(default_factory=dict, description="Optional structured readings.")


class InspectionOutMVP(BaseModel):
    """MVP: Inspection response."""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(..., description="Inspection id.")
    asset_id: int = Field(..., description="Asset id.")
    condition_rating: int = Field(..., ge=1, le=5, description="Condition rating 1..5.")
    observations: Optional[str] = Field(None, description="Observations.")
    photo_path: Optional[str] = Field(None, description="Relative photo path.")
    timestamp: datetime = Field(..., description="Timestamp.")
    readings: dict[str, Any] = Field(default_factory=dict, description="Readings payload.")


class AlertOutMVP(BaseModel):
    """MVP: Alert response."""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(..., description="Alert id.")
    asset_id: int = Field(..., description="Asset id.")
    type: str = Field(..., description="Alert type.")
    priority: str = Field(..., description="Priority string (e.g. high/medium/low).")
    created_at: datetime = Field(..., description="Creation timestamp.")


class WorkOrderCreateFromAlertMVP(BaseModel):
    """MVP: Create a work order from an existing alert."""

    alert_id: int = Field(..., description="Alert id to create work order for.")
    description: Optional[str] = Field(None, description="Work order description override.")
    assignee: Optional[str] = Field(None, description="Assignee name (string for MVP).")


class WorkOrderOutMVP(BaseModel):
    """MVP: Work order response."""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(..., description="Work order id.")
    asset_id: int = Field(..., description="Asset id.")
    description: str = Field(..., description="Work description.")
    status: WorkOrderStatus = Field(..., description="Status.")
    assignee: Optional[str] = Field(None, description="Assignee.")
    created_at: datetime = Field(..., description="Created timestamp.")
    updated_at: datetime = Field(..., description="Updated timestamp.")


class WorkOrderStatusPatchMVP(BaseModel):
    """MVP: Patch work order status request."""

    status: WorkOrderStatus = Field(..., description="New status.")


class TimelineEventOutMVP(BaseModel):
    """MVP: Timeline event response."""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(..., description="Event id.")
    asset_id: int = Field(..., description="Asset id.")
    event_type: TimelineEventType = Field(..., description="Event type.")
    description: str = Field(..., description="Description.")
    timestamp: datetime = Field(..., description="Timestamp.")
    inspection_id: Optional[int] = Field(None, description="Inspection id (optional).")
    alert_id: Optional[int] = Field(None, description="Alert id (optional).")
    work_order_id: Optional[int] = Field(None, description="Work order id (optional).")


class HealthStatusCountsMVP(BaseModel):
    """MVP: Counts by traffic-light health status."""

    green: int = Field(0, ge=0, description="Count of green assets (>=70).")
    amber: int = Field(0, ge=0, description="Count of amber assets (40..69).")
    red: int = Field(0, ge=0, description="Count of red assets (<40).")


class DashboardOutMVP(BaseModel):
    """MVP: Dashboard KPI response."""

    total_assets: int = Field(..., ge=0, description="Total assets.")
    health_status_counts: HealthStatusCountsMVP = Field(
        ..., description="Counts of assets by health bucket."
    )
    overdue_maintenance: int = Field(
        ..., ge=0, description="Count of assets overdue for maintenance (heuristic)."
    )
    open_work_orders: int = Field(..., ge=0, description="Count of open work orders.")


# ============================================================================
# Existing richer schemas (kept intact for future steps)
# ============================================================================


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


class AssetBase(BaseModel):
    """Common asset fields (richer schema)."""

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
    """Asset response (richer schema)."""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(..., description="Asset id.")
    health_score: float = Field(..., ge=0, le=100, description="Current health score (0-100).")
    last_inspected_at: Optional[datetime] = Field(None, description="Timestamp of last inspection.")
    created_at: datetime = Field(..., description="Created timestamp.")
    updated_at: datetime = Field(..., description="Updated timestamp.")


class InspectionPhotoOut(BaseModel):
    """Inspection photo metadata (richer schema)."""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(..., description="Photo id.")
    file_key: str = Field(..., description="Storage key/path for photo.")
    original_filename: Optional[str] = Field(None, description="Original filename.")
    content_type: Optional[str] = Field(None, description="MIME content-type.")
    created_at: datetime = Field(..., description="Upload timestamp.")
    url: Optional[str] = Field(None, description="Convenience URL for downloading/previewing.")


class InspectionBase(BaseModel):
    """Common inspection fields (richer schema)."""

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
    """Inspection response (richer schema)."""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(..., description="Inspection id.")
    inspector_user_id: Optional[int] = Field(None, description="Inspector user id.")
    created_at: datetime = Field(..., description="Created timestamp.")
    photos: list[InspectionPhotoOut] = Field(default_factory=list, description="Associated photos.")


class AlertBase(BaseModel):
    """Common alert fields (richer schema)."""

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
    """Alert response (richer schema)."""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(..., description="Alert id.")
    created_at: datetime = Field(..., description="Created timestamp.")
    resolved_at: Optional[datetime] = Field(None, description="Resolved timestamp.")


class WorkOrderBase(BaseModel):
    """Common work order fields (richer schema)."""

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
    """Work order response (richer schema)."""

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


class TimelineEventOut(BaseModel):
    """Timeline event response (richer schema)."""

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
    """Top-level dashboard KPI response (richer schema)."""

    total_assets: int = Field(..., ge=0, description="Total assets count.")
    avg_health_score: float = Field(..., ge=0, le=100, description="Average health score.")
    assets_at_risk: int = Field(..., ge=0, description="Assets with low health score.")
    open_alerts: int = Field(..., ge=0, description="Count of active alerts.")
    open_work_orders: int = Field(..., ge=0, description="Count of open/in-progress work orders.")


class DashboardOut(BaseModel):
    """Dashboard response containing KPIs and prioritized lists (richer schema)."""

    metrics: DashboardMetrics = Field(..., description="Key performance metrics.")
    top_risk_assets: list[AssetOut] = Field(default_factory=list, description="Assets with lowest health.")
    recent_alerts: list[AlertOut] = Field(default_factory=list, description="Recent active alerts.")
    upcoming_work_orders: list[WorkOrderOut] = Field(
        default_factory=list, description="Work orders prioritized by due date/priority."
    )
