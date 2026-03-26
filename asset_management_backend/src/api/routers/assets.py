"""Assets router.

MVP endpoints:
- GET /assets
- POST /assets
- GET /assets/{id}
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from api.db.deps import get_db
from api.db.models import Asset
from api.routers._common import not_found
from api.schemas import AssetCreateMVP, AssetOutMVP

router = APIRouter(prefix="/assets", tags=["Assets"])


@router.get(
    "",
    summary="List assets",
    description="List assets with optional filters (type/location/search).",
    response_model=list[AssetOutMVP],
    operation_id="assets_list",
)
# PUBLIC_INTERFACE
def list_assets(
    q: Optional[str] = Query(
        None, description="Substring search across tag/name/type/location/manufacturer."
    ),
    asset_type: Optional[str] = Query(None, description="Filter by asset type."),
    location: Optional[str] = Query(None, description="Filter by location."),
    db: Session = Depends(get_db),
) -> list[AssetOutMVP]:
    """List assets.

    Note: Auth is intentionally omitted for MVP demo. Add Depends(get_current_user)
    later without changing route signatures.
    """
    stmt = select(Asset)

    if q:
        like = f"%{q}%"
        stmt = stmt.where(
            or_(
                Asset.asset_tag.ilike(like),
                Asset.name.ilike(like),
                Asset.asset_type.ilike(like),
                Asset.location.ilike(like),
                Asset.manufacturer.ilike(like),
            )
        )
    if asset_type:
        stmt = stmt.where(Asset.asset_type == asset_type)
    if location:
        stmt = stmt.where(Asset.location == location)

    stmt = stmt.order_by(Asset.id.asc())
    assets = list(db.execute(stmt).scalars().all())
    return [AssetOutMVP.model_validate(a) for a in assets]


@router.post(
    "",
    summary="Create asset",
    description="Create an asset record in the register.",
    response_model=AssetOutMVP,
    status_code=status.HTTP_201_CREATED,
    operation_id="assets_create",
)
# PUBLIC_INTERFACE
def create_asset(payload: AssetCreateMVP, db: Session = Depends(get_db)) -> AssetOutMVP:
    """Create a new asset."""
    existing = (
        db.execute(select(Asset).where(Asset.asset_tag == payload.asset_tag))
        .scalars()
        .first()
    )
    if existing:
        # Keep error shape simple for MVP
        from fastapi import HTTPException

        raise HTTPException(status_code=400, detail="asset_tag already exists")

    asset = Asset(
        asset_tag=payload.asset_tag,
        name=payload.name,
        asset_type=payload.asset_type,
        location=payload.location,
        manufacturer=payload.manufacturer,
        installation_date=payload.installation_date,
        last_service_date=payload.last_service_date,
        # health_score computed later via inspections; default 100 on insert
        health_score=payload.health_score if payload.health_score is not None else 100.0,
    )
    # Ensure timestamps exist even if DB defaults handle them; helps SQLite/dev too.
    now = datetime.utcnow()
    if getattr(asset, "created_at", None) is None:
        setattr(asset, "created_at", now)  # for compatibility if column exists
    if getattr(asset, "updated_at", None) is None:
        setattr(asset, "updated_at", now)

    db.add(asset)
    db.commit()
    db.refresh(asset)
    return AssetOutMVP.model_validate(asset)


@router.get(
    "/{asset_id}",
    summary="Retrieve asset",
    description="Retrieve a single asset by id.",
    response_model=AssetOutMVP,
    operation_id="assets_get",
)
# PUBLIC_INTERFACE
def get_asset(asset_id: int, db: Session = Depends(get_db)) -> AssetOutMVP:
    """Get an asset by id."""
    asset = db.get(Asset, asset_id)
    if asset is None:
        raise not_found("Asset")
    return AssetOutMVP.model_validate(asset)
