"""FastAPI app entrypoint for the Asset Health & Maintenance Platform (MVP).

Step 03.01 (source-of-truth from attachment) requires demo-ready endpoints for:
- Assets (list/create/get)
- Inspections (log inspection with photo upload)
- Health score computation + auto-alert generation (health_score < 40)
- Alerts (list)
- Work orders (create from alert, update status)
- Timeline (per-asset)
- Dashboard KPIs

Environment variables (see .env.example):
- DATABASE_URL (or POSTGRES_URL)
- UPLOAD_DIR

Auth/JWT variables exist but are optional for the MVP.
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routers import alerts, assets, dashboard, files, inspections, timeline, workorders
from api.schemas import APIMessage

openapi_tags = [
    {"name": "Health", "description": "Service health checks."},
    {"name": "Assets", "description": "Asset register and health status."},
    {"name": "Inspections", "description": "Inspection logging with photo upload."},
    {"name": "Alerts", "description": "Auto alerts for at-risk assets."},
    {"name": "Work Orders", "description": "Work order lifecycle for maintenance."},
    {"name": "Timeline", "description": "Chronological asset timeline events."},
    {"name": "Dashboard", "description": "Dashboard KPIs."},
    {"name": "Files", "description": "Serving uploaded inspection photos."},
]

app = FastAPI(
    title="Asset Health & Maintenance Platform API",
    description="Demo-ready backend for asset health tracking and predictive maintenance.",
    version="0.3.1",
    openapi_tags=openapi_tags,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tighten in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get(
    "/",
    tags=["Health"],
    summary="Health check",
    description="Basic health check endpoint.",
    response_model=APIMessage,
    operation_id="health_check",
)
# PUBLIC_INTERFACE
def health_check() -> APIMessage:
    """Return a basic service health response."""
    return APIMessage(message="Healthy")


# Routers (MVP)
app.include_router(assets.router)
app.include_router(inspections.router)
app.include_router(alerts.router)
app.include_router(workorders.router)
app.include_router(dashboard.router)
app.include_router(timeline.router)
app.include_router(files.router)

# TODO(auth): Add JWT + RBAC dependencies once required; endpoints are structured as routers
# so this can be added via dependencies per-router without changing business logic.
