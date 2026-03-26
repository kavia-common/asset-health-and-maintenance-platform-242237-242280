"""Initial schema for asset health & maintenance platform.

Revision ID: 0001_initial_schema
Revises: 
Create Date: 2026-03-26

"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# Alembic identifiers
revision = "0001_initial_schema"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Enums
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("full_name", sa.String(length=200), nullable=True),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column(
            "role",
            sa.Enum("admin", "manager", "technician", name="user_role"),
            nullable=False,
        ),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    op.create_table(
        "assets",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("asset_tag", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("asset_type", sa.String(length=100), nullable=True),
        sa.Column("location", sa.String(length=200), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "criticality",
            sa.Enum("low", "medium", "high", name="asset_criticality"),
            server_default="medium",
            nullable=False,
        ),
        sa.Column("health_score", sa.Float(), server_default="100", nullable=False),
        sa.Column("last_inspected_at", sa.DateTime(timezone=True), nullable=True),
        # Column name remains "metadata"; ORM attribute is `asset_metadata` to avoid clashing
        # with SQLAlchemy DeclarativeBase.metadata.
        sa.Column("metadata", sa.JSON(), server_default=sa.text("'{}'::json"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_assets_asset_tag", "assets", ["asset_tag"], unique=True)
    op.create_index("ix_assets_type_location", "assets", ["asset_type", "location"], unique=False)

    op.create_table(
        "work_orders",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("asset_id", sa.Integer(), sa.ForeignKey("assets.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("priority", sa.Integer(), server_default="3", nullable=False),
        sa.Column(
            "status",
            sa.Enum("open", "in_progress", "done", "canceled", name="work_order_status"),
            server_default="open",
            nullable=False,
        ),
        sa.Column("created_by_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("assigned_to_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("due_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_work_orders_asset_id", "work_orders", ["asset_id"], unique=False)
    op.create_index("ix_work_orders_status", "work_orders", ["status"], unique=False)
    op.create_index("ix_work_orders_created_by_user_id", "work_orders", ["created_by_user_id"], unique=False)
    op.create_index("ix_work_orders_assigned_to_user_id", "work_orders", ["assigned_to_user_id"], unique=False)

    op.create_table(
        "inspections",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("asset_id", sa.Integer(), sa.ForeignKey("assets.id", ondelete="CASCADE"), nullable=False),
        sa.Column("inspector_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column(
            "inspection_type",
            sa.Enum("routine", "detailed", "emergency", name="inspection_type"),
            server_default="routine",
            nullable=False,
        ),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("readings", sa.JSON(), server_default=sa.text("'{}'::json"), nullable=False),
        sa.Column("assessed_health_score", sa.Float(), nullable=True),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_inspections_asset_id", "inspections", ["asset_id"], unique=False)
    op.create_index("ix_inspections_inspector_user_id", "inspections", ["inspector_user_id"], unique=False)
    op.create_index("ix_inspections_asset_occurred_at", "inspections", ["asset_id", "occurred_at"], unique=False)

    op.create_table(
        "inspection_photos",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("inspection_id", sa.Integer(), sa.ForeignKey("inspections.id", ondelete="CASCADE"), nullable=False),
        sa.Column("file_key", sa.String(length=512), nullable=False),
        sa.Column("original_filename", sa.String(length=255), nullable=True),
        sa.Column("content_type", sa.String(length=100), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("inspection_id", "file_key", name="uq_inspection_photo_inspection_file_key"),
    )
    op.create_index("ix_inspection_photos_inspection_id", "inspection_photos", ["inspection_id"], unique=False)
    op.create_index("ix_inspection_photos_file_key", "inspection_photos", ["file_key"], unique=True)

    op.create_table(
        "alerts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("asset_id", sa.Integer(), sa.ForeignKey("assets.id", ondelete="CASCADE"), nullable=False),
        sa.Column(
            "severity",
            sa.Enum("low", "medium", "high", "critical", name="alert_severity"),
            server_default="medium",
            nullable=False,
        ),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("related_work_order_id", sa.Integer(), sa.ForeignKey("work_orders.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_alerts_asset_id", "alerts", ["asset_id"], unique=False)
    op.create_index("ix_alerts_related_work_order_id", "alerts", ["related_work_order_id"], unique=False)

    op.create_table(
        "work_order_status_history",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("work_order_id", sa.Integer(), sa.ForeignKey("work_orders.id", ondelete="CASCADE"), nullable=False),
        sa.Column(
            "from_status",
            sa.Enum("open", "in_progress", "done", "canceled", name="work_order_status"),
            nullable=True,
        ),
        sa.Column(
            "to_status",
            sa.Enum("open", "in_progress", "done", "canceled", name="work_order_status"),
            nullable=False,
        ),
        sa.Column("changed_by_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("changed_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_work_order_status_history_work_order_id", "work_order_status_history", ["work_order_id"], unique=False)
    op.create_index("ix_work_order_status_history_changed_by_user_id", "work_order_status_history", ["changed_by_user_id"], unique=False)

    op.create_table(
        "timeline_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("asset_id", sa.Integer(), sa.ForeignKey("assets.id", ondelete="CASCADE"), nullable=False),
        sa.Column(
            "event_type",
            sa.Enum(
                "asset_created",
                "inspection_logged",
                "alert_raised",
                "work_order_created",
                "work_order_status_changed",
                "note",
                name="timeline_event_type",
            ),
            nullable=False,
        ),
        sa.Column("inspection_id", sa.Integer(), sa.ForeignKey("inspections.id", ondelete="SET NULL"), nullable=True),
        sa.Column("alert_id", sa.Integer(), sa.ForeignKey("alerts.id", ondelete="SET NULL"), nullable=True),
        sa.Column("work_order_id", sa.Integer(), sa.ForeignKey("work_orders.id", ondelete="SET NULL"), nullable=True),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("message", sa.Text(), nullable=True),
        sa.Column("extra", sa.JSON(), server_default=sa.text("'{}'::json"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_timeline_events_asset_id", "timeline_events", ["asset_id"], unique=False)
    op.create_index("ix_timeline_events_event_type", "timeline_events", ["event_type"], unique=False)
    op.create_index("ix_timeline_events_inspection_id", "timeline_events", ["inspection_id"], unique=False)
    op.create_index("ix_timeline_events_alert_id", "timeline_events", ["alert_id"], unique=False)
    op.create_index("ix_timeline_events_work_order_id", "timeline_events", ["work_order_id"], unique=False)
    op.create_index("ix_timeline_events_created_at", "timeline_events", ["created_at"], unique=False)


def downgrade() -> None:
    # Drop tables first (reverse dependency order)
    op.drop_index("ix_timeline_events_created_at", table_name="timeline_events")
    op.drop_index("ix_timeline_events_work_order_id", table_name="timeline_events")
    op.drop_index("ix_timeline_events_alert_id", table_name="timeline_events")
    op.drop_index("ix_timeline_events_inspection_id", table_name="timeline_events")
    op.drop_index("ix_timeline_events_event_type", table_name="timeline_events")
    op.drop_index("ix_timeline_events_asset_id", table_name="timeline_events")
    op.drop_table("timeline_events")

    op.drop_index("ix_work_order_status_history_changed_by_user_id", table_name="work_order_status_history")
    op.drop_index("ix_work_order_status_history_work_order_id", table_name="work_order_status_history")
    op.drop_table("work_order_status_history")

    op.drop_index("ix_alerts_related_work_order_id", table_name="alerts")
    op.drop_index("ix_alerts_asset_id", table_name="alerts")
    op.drop_table("alerts")

    op.drop_index("ix_inspection_photos_file_key", table_name="inspection_photos")
    op.drop_index("ix_inspection_photos_inspection_id", table_name="inspection_photos")
    op.drop_table("inspection_photos")

    op.drop_index("ix_inspections_asset_occurred_at", table_name="inspections")
    op.drop_index("ix_inspections_inspector_user_id", table_name="inspections")
    op.drop_index("ix_inspections_asset_id", table_name="inspections")
    op.drop_table("inspections")

    op.drop_index("ix_work_orders_assigned_to_user_id", table_name="work_orders")
    op.drop_index("ix_work_orders_created_by_user_id", table_name="work_orders")
    op.drop_index("ix_work_orders_status", table_name="work_orders")
    op.drop_index("ix_work_orders_asset_id", table_name="work_orders")
    op.drop_table("work_orders")

    op.drop_index("ix_assets_type_location", table_name="assets")
    op.drop_index("ix_assets_asset_tag", table_name="assets")
    op.drop_table("assets")

    op.drop_index("ix_users_email", table_name="users")
    op.drop_table("users")

    # Drop enums (PostgreSQL)
    op.execute("DROP TYPE IF EXISTS timeline_event_type")
    op.execute("DROP TYPE IF EXISTS alert_severity")
    op.execute("DROP TYPE IF EXISTS inspection_type")
    op.execute("DROP TYPE IF EXISTS work_order_status")
    op.execute("DROP TYPE IF EXISTS asset_criticality")
    op.execute("DROP TYPE IF EXISTS user_role")
