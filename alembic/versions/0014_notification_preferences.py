"""Notification preferences (Phase 7.5).

Revision ID: 0014_notification_preferences
Revises: 0013_notification_devices_deliveries
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0014_notify_prefs"
down_revision = "0013_notify_devices"
branch_labels = None
depends_on = None

RLS_TABLE = "notification_preferences"


def upgrade() -> None:
    op.create_table(
        "notification_preferences",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("notification_type", sa.String(64), nullable=False),
        sa.Column("push_enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint(
            "tenant_id",
            "user_id",
            "notification_type",
            name="uq_notification_preferences_user_type",
        ),
        sa.UniqueConstraint("id", "tenant_id", name="uq_notification_preferences_id_tenant"),
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
    op.drop_table("notification_preferences")
