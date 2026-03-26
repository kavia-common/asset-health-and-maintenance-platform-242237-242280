"""FastAPI app entrypoint for the Asset Health & Maintenance Platform.

This module wires:
- DB-backed CRUD endpoints for assets, inspections (with photo upload), alerts, work orders.
- JWT authentication with role-based access control (RBAC).
- Health score recomputation and auto-alert generation on inspections.
- Timeline and dashboard aggregation endpoints.
- Static file serving for uploaded inspection photos.

Environment variables (see .env.example):
- DATABASE_URL (or POSTGRES_URL)
- JWT_SECRET
- ACCESS_TOKEN_EXPIRE_MINUTES (optional)
- UPLOAD_DIR (optional)

Run:
    uvicorn src.api.main:app --reload --port 8000
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from fastapi import (
    Depends,
    FastAPI,
    File,
    HTTPException,
    Query,
    Response,
    UploadFile,
    status,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from sqlalchemy import and_, desc, func, or_, select
from sqlalchemy.orm import Session

from api.core.security import (
    create_access_token,
    get_current_user,
    hash_password,
    require_roles,
    verify_password,
)
from api.db.deps import get_db
from api.db.models import (
    Alert,
    Asset,
    Inspection,
    InspectionPhoto,
    TimelineEvent,
    TimelineEventType,
    User,
    UserRole,
    WorkOrder,
    WorkOrderStatus,
)
from api.schemas import (
    AlertCreate,
    AlertOut,
    AlertUpdate,
    APIMessage,
    AssetCreate,
    AssetOut,
    AssetUpdate,
    DashboardMetrics,
    DashboardOut,
    InspectionCreate,
    InspectionOut,
    InspectionPhotoOut,
    LoginRequest,
    TimelineEventOut,
    TokenResponse,
    UserCreate,
    UserPublic,
    WorkOrderCreate,
    WorkOrderOut,
    WorkOrderStatusChange,
    WorkOrderUpdate,
)
from api.services import (
    create_timeline_event,
    get_recent_timeline_for_asset,
    recompute_asset_health_and_maybe_alert,
    set_work_order_status,
)
from api.storage import save_inspection_photo
from api.core.config import get_upload_dir

openapi_tags = [
    {"name": "Health", "description": "Service health and documentation helpers."},
    {"name": "Auth", "description": "Authentication and user management."},
    {"name": "Assets", "description": "Asset register and health status."},
    {"name": "Inspections", "description": "Inspection logging and photo uploads."},
    {"name": "Alerts", "description": "Alerting for at-risk assets."},
    {"name": "Work Orders", "description": "Maintenance work order lifecycle."},
    {"name": "Timeline", "description": "Asset history timeline aggregation."},
    {"name": "Dashboard", "description": "Dashboard metrics and prioritized lists."},
    {"name": "Files", "description": "Serving uploaded inspection photos."},
]

app = FastAPI(
    title="Asset Health & Maintenance Platform API",
    description=(
        "Backend API for utility asset health tracking and predictive maintenance.\n\n"
        "Auth: use /auth/login to obtain a JWT and then pass it as:\n"
        "  Authorization: Bearer <token>\n"
    ),
    version="0.1.0",
    openapi_tags=openapi_tags,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # For production, restrict this to known frontend origins.
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _not_found(entity: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"{entity} not found")


def _photo_to_out(photo: InspectionPhoto) -> InspectionPhotoOut:
    # Provide a stable URL to fetch file
    out = InspectionPhotoOut.model_validate(photo)
    out.url = f"/files/{photo.file_key}"
    return out


# -----------------------
# Health / docs helpers
# -----------------------
@app.get(
    "/",
    tags=["Health"],
    summary="Health check",
    description="Basic health check endpoint.",
    response_model=APIMessage,
    operation_id="health_check_root",
)
def health_check() -> APIMessage:
    """Return a basic service health response."""
    return APIMessage(message="Healthy")


@app.get(
    "/docs/auth",
    tags=["Health"],
    summary="Auth usage help",
    description="Quick guide for obtaining and using JWT tokens.",
    response_model=APIMessage,
    operation_id="docs_auth_help",
)
def docs_auth_help() -> APIMessage:
    """Return basic auth usage help."""
    return APIMessage(
        message=(
            "1) POST /auth/login with {email,password} to get access_token.\n"
            "2) Use header Authorization: Bearer <access_token> for protected endpoints.\n"
            "3) Roles: admin, manager, technician. Admin can manage users."
        )
    )


# -----------------------
# Auth / Users
# -----------------------
@app.post(
    "/auth/login",
    tags=["Auth"],
    summary="Login",
    description="Authenticate a user and return a JWT access token.",
    response_model=TokenResponse,
    operation_id="auth_login",
)
def login(payload: LoginRequest, db: Session = Depends(get_db)) -> TokenResponse:
    """Authenticate via email/password and return a JWT access token."""
    user = db.execute(select(User).where(User.email == payload.email)).scalar_one_or_none()
    if user is None or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    if not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    token, expires_in = create_access_token(subject=user.email, role=user.role.value, user_id=user.id)
    return TokenResponse(
        access_token=token,
        token_type="bearer",
        expires_in=expires_in,
        user=UserPublic.model_validate(user),
    )


@app.get(
    "/auth/me",
    tags=["Auth"],
    summary="Get current user",
    description="Return the currently authenticated user.",
    response_model=UserPublic,
    operation_id="auth_me",
)
def me(current_user: User = Depends(get_current_user)) -> UserPublic:
    """Return current user."""
    return UserPublic.model_validate(current_user)


@app.post(
    "/users",
    tags=["Auth"],
    summary="Create user (admin)",
    description="Create a new user account. Admin-only.",
    response_model=UserPublic,
    status_code=status.HTTP_201_CREATED,
    operation_id="users_create",
)
def create_user(
    payload: UserCreate,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles(UserRole.ADMIN)),
) -> UserPublic:
    """Create a new user (admin-only)."""
    existing = db.execute(select(User).where(User.email == payload.email)).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=400, detail="Email already exists")

    user = User(
        email=payload.email,
        full_name=payload.full_name,
        password_hash=hash_password(payload.password),
        role=payload.role,
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return UserPublic.model_validate(user)


# -----------------------
# Assets
# -----------------------
@app.get(
    "/assets",
    tags=["Assets"],
    summary="List assets",
    description="List assets with optional search/filter.",
    response_model=list[AssetOut],
    operation_id="assets_list",
)
def list_assets(
    q: Optional[str] = Query(None, description="Search by tag/name/type/location (substring)."),
    asset_type: Optional[str] = Query(None, description="Filter by asset type."),
    location: Optional[str] = Query(None, description="Filter by location."),
    min_health: Optional[float] = Query(None, ge=0, le=100, description="Minimum health score."),
    max_health: Optional[float] = Query(None, ge=0, le=100, description="Maximum health score."),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> list[AssetOut]:
    """List assets."""
    stmt = select(Asset)

    if q:
        like = f"%{q}%"
        stmt = stmt.where(
            or_(
                Asset.asset_tag.ilike(like),
                Asset.name.ilike(like),
                Asset.asset_type.ilike(like),
                Asset.location.ilike(like),
            )
        )
    if asset_type:
        stmt = stmt.where(Asset.asset_type == asset_type)
    if location:
        stmt = stmt.where(Asset.location == location)
    if min_health is not None:
        stmt = stmt.where(Asset.health_score >= float(min_health))
    if max_health is not None:
        stmt = stmt.where(Asset.health_score <= float(max_health))

    stmt = stmt.order_by(Asset.id.asc())
    assets = list(db.execute(stmt).scalars().all())
    return [AssetOut.model_validate(a) for a in assets]


@app.post(
    "/assets",
    tags=["Assets"],
    summary="Create asset",
    description="Create a new asset. Manager/admin-only.",
    response_model=AssetOut,
    status_code=status.HTTP_201_CREATED,
    operation_id="assets_create",
)
def create_asset(
    payload: AssetCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(UserRole.ADMIN, UserRole.MANAGER)),
) -> AssetOut:
    """Create an asset and emit a timeline event."""
    existing = db.execute(select(Asset).where(Asset.asset_tag == payload.asset_tag)).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=400, detail="asset_tag already exists")

    asset = Asset(
        asset_tag=payload.asset_tag,
        name=payload.name,
        asset_type=payload.asset_type,
        location=payload.location,
        description=payload.description,
        criticality=payload.criticality,
        metadata=payload.metadata,
    )
    db.add(asset)
    db.flush()  # allocate id

    create_timeline_event(
        db,
        asset_id=asset.id,
        event_type=TimelineEventType.ASSET_CREATED,
        title="Asset created",
        message=f"Created by user {user.id}",
        extra={"created_by_user_id": user.id},
    )

    db.commit()
    db.refresh(asset)
    return AssetOut.model_validate(asset)


@app.get(
    "/assets/{asset_id}",
    tags=["Assets"],
    summary="Get asset",
    description="Get asset by id.",
    response_model=AssetOut,
    operation_id="assets_get",
)
def get_asset(
    asset_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> AssetOut:
    """Get an asset by id."""
    asset = db.get(Asset, asset_id)
    if asset is None:
        raise _not_found("Asset")
    return AssetOut.model_validate(asset)


@app.patch(
    "/assets/{asset_id}",
    tags=["Assets"],
    summary="Update asset",
    description="Update asset fields. Manager/admin-only.",
    response_model=AssetOut,
    operation_id="assets_update",
)
def update_asset(
    asset_id: int,
    payload: AssetUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles(UserRole.ADMIN, UserRole.MANAGER)),
) -> AssetOut:
    """Update an asset."""
    asset = db.get(Asset, asset_id)
    if asset is None:
        raise _not_found("Asset")

    data = payload.model_dump(exclude_unset=True)
    for k, v in data.items():
        setattr(asset, k, v)

    db.commit()
    db.refresh(asset)
    return AssetOut.model_validate(asset)


@app.delete(
    "/assets/{asset_id}",
    tags=["Assets"],
    summary="Delete asset",
    description="Delete asset. Admin-only.",
    status_code=status.HTTP_204_NO_CONTENT,
    operation_id="assets_delete",
)
def delete_asset(
    asset_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles(UserRole.ADMIN)),
) -> Response:
    """Delete asset and cascade dependent records."""
    asset = db.get(Asset, asset_id)
    if asset is None:
        raise _not_found("Asset")
    db.delete(asset)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# -----------------------
# Inspections
# -----------------------
@app.get(
    "/inspections",
    tags=["Inspections"],
    summary="List inspections",
    description="List inspections, optionally filtered by asset.",
    response_model=list[InspectionOut],
    operation_id="inspections_list",
)
def list_inspections(
    asset_id: Optional[int] = Query(None, description="Filter by asset id."),
    limit: int = Query(50, ge=1, le=200, description="Max items."),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> list[InspectionOut]:
    """List inspections."""
    stmt = select(Inspection).order_by(desc(Inspection.occurred_at)).limit(limit)
    if asset_id is not None:
        stmt = stmt.where(Inspection.asset_id == asset_id)

    inspections = list(db.execute(stmt).scalars().all())

    out: list[InspectionOut] = []
    for ins in inspections:
        o = InspectionOut.model_validate(ins)
        o.photos = [_photo_to_out(p) for p in ins.photos]
        out.append(o)
    return out


@app.post(
    "/inspections",
    tags=["Inspections"],
    summary="Create inspection",
    description="Log an inspection. Technician/manager/admin.",
    response_model=InspectionOut,
    status_code=status.HTTP_201_CREATED,
    operation_id="inspections_create",
)
def create_inspection(
    payload: InspectionCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(UserRole.ADMIN, UserRole.MANAGER, UserRole.TECHNICIAN)),
) -> InspectionOut:
    """Create an inspection, recompute health score, and auto-create/resolve alerts."""
    asset = db.get(Asset, payload.asset_id)
    if asset is None:
        raise _not_found("Asset")

    ins = Inspection(
        asset_id=payload.asset_id,
        inspector_user_id=user.id,
        inspection_type=payload.inspection_type,
        notes=payload.notes,
        readings=payload.readings,
        assessed_health_score=payload.assessed_health_score,
        occurred_at=payload.occurred_at,
    )
    db.add(ins)
    db.flush()  # alloc inspection id

    create_timeline_event(
        db,
        asset_id=asset.id,
        event_type=TimelineEventType.INSPECTION_LOGGED,
        title="Inspection logged",
        message=f"{payload.inspection_type.value} inspection by user {user.id}",
        inspection_id=ins.id,
        extra={"assessed_health_score": payload.assessed_health_score},
    )

    recompute_asset_health_and_maybe_alert(db, asset=asset, actor=user, inspection=ins)

    db.commit()
    db.refresh(ins)

    out = InspectionOut.model_validate(ins)
    out.photos = [_photo_to_out(p) for p in ins.photos]
    return out


@app.post(
    "/inspections/{inspection_id}/photos",
    tags=["Inspections"],
    summary="Upload inspection photo",
    description="Upload a photo for an inspection (multipart/form-data). Technician/manager/admin.",
    response_model=InspectionPhotoOut,
    status_code=status.HTTP_201_CREATED,
    operation_id="inspections_upload_photo",
)
def upload_inspection_photo(
    inspection_id: int,
    file: UploadFile = File(..., description="Image file to upload."),
    db: Session = Depends(get_db),
    _: User = Depends(require_roles(UserRole.ADMIN, UserRole.MANAGER, UserRole.TECHNICIAN)),
) -> InspectionPhotoOut:
    """Upload an inspection photo and store metadata in DB."""
    ins = db.get(Inspection, inspection_id)
    if ins is None:
        raise _not_found("Inspection")

    file_key, content_type = save_inspection_photo(inspection_id=inspection_id, file=file)
    photo = InspectionPhoto(
        inspection_id=inspection_id,
        file_key=file_key,
        original_filename=file.filename,
        content_type=content_type,
    )
    db.add(photo)
    db.commit()
    db.refresh(photo)
    return _photo_to_out(photo)


# -----------------------
# Alerts
# -----------------------
@app.get(
    "/alerts",
    tags=["Alerts"],
    summary="List alerts",
    description="List alerts with optional filtering.",
    response_model=list[AlertOut],
    operation_id="alerts_list",
)
def list_alerts(
    asset_id: Optional[int] = Query(None, description="Filter by asset id."),
    is_active: Optional[bool] = Query(True, description="Filter by active state."),
    limit: int = Query(100, ge=1, le=200, description="Max items."),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> list[AlertOut]:
    """List alerts."""
    stmt = select(Alert).order_by(desc(Alert.created_at)).limit(limit)
    if asset_id is not None:
        stmt = stmt.where(Alert.asset_id == asset_id)
    if is_active is not None:
        stmt = stmt.where(Alert.is_active.is_(bool(is_active)))

    alerts = list(db.execute(stmt).scalars().all())
    return [AlertOut.model_validate(a) for a in alerts]


@app.post(
    "/alerts",
    tags=["Alerts"],
    summary="Create alert",
    description="Create a manual alert. Manager/admin-only.",
    response_model=AlertOut,
    status_code=status.HTTP_201_CREATED,
    operation_id="alerts_create",
)
def create_alert(
    payload: AlertCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(UserRole.ADMIN, UserRole.MANAGER)),
) -> AlertOut:
    """Create a manual alert and emit a timeline event."""
    asset = db.get(Asset, payload.asset_id)
    if asset is None:
        raise _not_found("Asset")

    alert = Alert(
        asset_id=payload.asset_id,
        severity=payload.severity,
        title=payload.title,
        description=payload.description,
        is_active=payload.is_active,
        related_work_order_id=payload.related_work_order_id,
    )
    db.add(alert)
    db.flush()

    create_timeline_event(
        db,
        asset_id=payload.asset_id,
        event_type=TimelineEventType.ALERT_RAISED,
        title="Alert raised",
        message=payload.title,
        alert_id=alert.id,
        extra={"created_by_user_id": user.id, "severity": payload.severity.value},
    )

    db.commit()
    db.refresh(alert)
    return AlertOut.model_validate(alert)


@app.patch(
    "/alerts/{alert_id}",
    tags=["Alerts"],
    summary="Update/resolve alert",
    description="Update alert fields, including marking inactive/resolved. Manager/admin-only.",
    response_model=AlertOut,
    operation_id="alerts_update",
)
def update_alert(
    alert_id: int,
    payload: AlertUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles(UserRole.ADMIN, UserRole.MANAGER)),
) -> AlertOut:
    """Update an alert."""
    alert = db.get(Alert, alert_id)
    if alert is None:
        raise _not_found("Alert")

    data = payload.model_dump(exclude_unset=True)
    for k, v in data.items():
        setattr(alert, k, v)

    # If set inactive without resolved_at, set resolved_at now
    if ("is_active" in data) and (data["is_active"] is False) and (alert.resolved_at is None):
        alert.resolved_at = _utcnow()

    db.commit()
    db.refresh(alert)
    return AlertOut.model_validate(alert)


# -----------------------
# Work orders
# -----------------------
@app.get(
    "/work-orders",
    tags=["Work Orders"],
    summary="List work orders",
    description="List work orders with optional filtering.",
    response_model=list[WorkOrderOut],
    operation_id="work_orders_list",
)
def list_work_orders(
    asset_id: Optional[int] = Query(None, description="Filter by asset id."),
    status_filter: Optional[WorkOrderStatus] = Query(None, description="Filter by status."),
    assigned_to_user_id: Optional[int] = Query(None, description="Filter by assigned user id."),
    limit: int = Query(100, ge=1, le=200, description="Max items."),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> list[WorkOrderOut]:
    """List work orders."""
    stmt = select(WorkOrder).order_by(desc(WorkOrder.created_at)).limit(limit)
    if asset_id is not None:
        stmt = stmt.where(WorkOrder.asset_id == asset_id)
    if status_filter is not None:
        stmt = stmt.where(WorkOrder.status == status_filter)
    if assigned_to_user_id is not None:
        stmt = stmt.where(WorkOrder.assigned_to_user_id == assigned_to_user_id)

    rows = list(db.execute(stmt).scalars().all())
    return [WorkOrderOut.model_validate(w) for w in rows]


@app.post(
    "/work-orders",
    tags=["Work Orders"],
    summary="Create work order",
    description="Create a work order. Manager/admin-only.",
    response_model=WorkOrderOut,
    status_code=status.HTTP_201_CREATED,
    operation_id="work_orders_create",
)
def create_work_order(
    payload: WorkOrderCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(UserRole.ADMIN, UserRole.MANAGER)),
) -> WorkOrderOut:
    """Create a work order and emit a timeline event."""
    asset = db.get(Asset, payload.asset_id)
    if asset is None:
        raise _not_found("Asset")

    wo = WorkOrder(
        asset_id=payload.asset_id,
        title=payload.title,
        description=payload.description,
        priority=payload.priority,
        status=payload.status,
        assigned_to_user_id=payload.assigned_to_user_id,
        due_date=payload.due_date,
        created_by_user_id=user.id,
    )
    db.add(wo)
    db.flush()

    create_timeline_event(
        db,
        asset_id=payload.asset_id,
        event_type=TimelineEventType.WORK_ORDER_CREATED,
        title="Work order created",
        message=payload.title,
        work_order_id=wo.id,
        extra={"created_by_user_id": user.id, "priority": payload.priority},
    )

    db.commit()
    db.refresh(wo)
    return WorkOrderOut.model_validate(wo)


@app.patch(
    "/work-orders/{work_order_id}",
    tags=["Work Orders"],
    summary="Update work order",
    description="Update a work order fields. Manager/admin-only.",
    response_model=WorkOrderOut,
    operation_id="work_orders_update",
)
def update_work_order(
    work_order_id: int,
    payload: WorkOrderUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles(UserRole.ADMIN, UserRole.MANAGER)),
) -> WorkOrderOut:
    """Update work order."""
    wo = db.get(WorkOrder, work_order_id)
    if wo is None:
        raise _not_found("Work order")

    data = payload.model_dump(exclude_unset=True)
    for k, v in data.items():
        setattr(wo, k, v)

    db.commit()
    db.refresh(wo)
    return WorkOrderOut.model_validate(wo)


@app.post(
    "/work-orders/{work_order_id}/status",
    tags=["Work Orders"],
    summary="Change work order status",
    description="Change work order status and create a status history record. Technician/manager/admin.",
    response_model=WorkOrderOut,
    operation_id="work_orders_change_status",
)
def change_work_order_status(
    work_order_id: int,
    payload: WorkOrderStatusChange,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(UserRole.ADMIN, UserRole.MANAGER, UserRole.TECHNICIAN)),
) -> WorkOrderOut:
    """Change work order status and emit timeline event."""
    wo = db.get(WorkOrder, work_order_id)
    if wo is None:
        raise _not_found("Work order")

    set_work_order_status(db, work_order=wo, to_status=payload.to_status, actor=user, note=payload.note)
    db.commit()
    db.refresh(wo)
    return WorkOrderOut.model_validate(wo)


# -----------------------
# Timeline
# -----------------------
@app.get(
    "/assets/{asset_id}/timeline",
    tags=["Timeline"],
    summary="Get asset timeline",
    description="Get recent timeline events for an asset.",
    response_model=list[TimelineEventOut],
    operation_id="timeline_get_for_asset",
)
def get_asset_timeline(
    asset_id: int,
    limit: int = Query(50, ge=1, le=200, description="Max items."),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> list[TimelineEventOut]:
    """Return recent timeline events for an asset."""
    asset = db.get(Asset, asset_id)
    if asset is None:
        raise _not_found("Asset")
    events = get_recent_timeline_for_asset(db, asset_id=asset_id, limit=limit)
    return [TimelineEventOut.model_validate(e) for e in events]


# -----------------------
# Dashboard
# -----------------------
@app.get(
    "/dashboard",
    tags=["Dashboard"],
    summary="Get dashboard data",
    description="Aggregated metrics and prioritized lists for the management dashboard.",
    response_model=DashboardOut,
    operation_id="dashboard_get",
)
def get_dashboard(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> DashboardOut:
    """Return dashboard metrics and key lists."""
    total_assets = int(db.execute(select(func.count(Asset.id))).scalar_one())
    avg_health = float(db.execute(select(func.coalesce(func.avg(Asset.health_score), 100.0))).scalar_one())
    assets_at_risk = int(db.execute(select(func.count(Asset.id)).where(Asset.health_score <= 70)).scalar_one())

    open_alerts = int(
        db.execute(select(func.count(Alert.id)).where(Alert.is_active.is_(True))).scalar_one()
    )
    open_work_orders = int(
        db.execute(
            select(func.count(WorkOrder.id)).where(
                WorkOrder.status.in_([WorkOrderStatus.OPEN, WorkOrderStatus.IN_PROGRESS])
            )
        ).scalar_one()
    )

    top_risk_assets = list(
        db.execute(select(Asset).order_by(Asset.health_score.asc()).limit(5)).scalars().all()
    )
    recent_alerts = list(
        db.execute(
            select(Alert).where(Alert.is_active.is_(True)).order_by(desc(Alert.created_at)).limit(10)
        ).scalars().all()
    )
    upcoming_work_orders = list(
        db.execute(
            select(WorkOrder)
            .where(WorkOrder.status.in_([WorkOrderStatus.OPEN, WorkOrderStatus.IN_PROGRESS]))
            .order_by(
                # Due date first (nulls last), then priority
                WorkOrder.due_date.asc().nullslast(),
                WorkOrder.priority.asc(),
                WorkOrder.created_at.desc(),
            )
            .limit(10)
        ).scalars().all()
    )

    metrics = DashboardMetrics(
        total_assets=total_assets,
        avg_health_score=max(0.0, min(100.0, avg_health)),
        assets_at_risk=assets_at_risk,
        open_alerts=open_alerts,
        open_work_orders=open_work_orders,
    )

    return DashboardOut(
        metrics=metrics,
        top_risk_assets=[AssetOut.model_validate(a) for a in top_risk_assets],
        recent_alerts=[AlertOut.model_validate(a) for a in recent_alerts],
        upcoming_work_orders=[WorkOrderOut.model_validate(w) for w in upcoming_work_orders],
    )


# -----------------------
# Files (photo serving)
# -----------------------
@app.get(
    "/files/{file_key:path}",
    tags=["Files"],
    summary="Serve uploaded file",
    description="Serve an uploaded inspection photo by file_key.",
    operation_id="files_get",
)
def serve_file(
    file_key: str,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """Serve a stored file, only if referenced by an inspection photo record."""
    # Authorization-by-reference: must exist in DB
    photo = db.execute(select(InspectionPhoto).where(InspectionPhoto.file_key == file_key)).scalar_one_or_none()
    if photo is None:
        raise _not_found("File")

    root = Path(get_upload_dir()).resolve()
    path = (root / file_key).resolve()
    # Prevent directory traversal: resolved path must stay within upload root.
    if not str(path).startswith(str(root)):
        raise HTTPException(status_code=400, detail="Invalid file key")

    if not path.exists():
        raise _not_found("File")

    return FileResponse(path=str(path), media_type=photo.content_type or "application/octet-stream")
