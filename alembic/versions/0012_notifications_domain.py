"""Notification inbox domain (Phase 7.1).

Revision ID: 0012_notifications_domain
Revises: 0011_parent_gps_read
Create Date: 2026-09-19
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0012_notifications_domain"
down_revision = "0011_parent_gps_read"
branch_labels = None
depends_on = None

RLS_TABLE = "notifications"


def upgrade() -> None:
    op.create_table(
        "notifications",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("recipient_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("notification_type", sa.String(64), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("correlation_id", sa.String(64), nullable=True),
        sa.Column("idempotency_key", sa.String(256), nullable=False),
        sa.Column("schema_version", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.Column("delivery_status", sa.String(32), nullable=False, server_default="pending"),
        sa.Column("reference_type", sa.String(64), nullable=True),
        sa.Column("reference_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("tenant_id", "idempotency_key", name="uq_notifications_tenant_idempotency"),
        sa.UniqueConstraint("id", "tenant_id", name="uq_notifications_id_tenant"),
        sa.CheckConstraint(
            "delivery_status IN ('pending', 'queued', 'sent', 'failed', "
            "'skipped_preference', 'skipped_no_device')",
            name="ck_notifications_delivery_status",
        ),
    )
    op.create_index(
        "ix_notifications_tenant_recipient_created",
        "notifications",
        ["tenant_id", "recipient_user_id", "created_at"],
    )

    op.execute(f"ALTER TABLE {RLS_TABLE} ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {RLS_TABLE} FORCE ROW LEVEL SECURITY")
    op.execute(
        f"""
        CREATE POLICY tenant_isolation ON {RLS_TABLE}
          USING (
            tenant_id IS NOT DISTINCT FROM NULLIF(current_setting('app.tenant_id', true), '')::uuid
          )
          WITH CHECK (
            tenant_id IS NOT DISTINCT FROM NULLIF(current_setting('app.tenant_id', true), '')::uuid
          )
        """
    )
    op.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON {RLS_TABLE} TO schoolpass_app")


def downgrade() -> None:
    op.execute(f"DROP POLICY IF EXISTS tenant_isolation ON {RLS_TABLE}")
    op.drop_table("notifications")
