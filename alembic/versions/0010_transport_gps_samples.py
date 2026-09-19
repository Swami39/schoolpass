"""Transport GPS location samples.

Revision ID: 0010_transport_gps
Revises: 0009_nfc_boarding_index
Create Date: 2026-09-19
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0010_transport_gps"
down_revision = "0009_nfc_boarding_index"
branch_labels = None
depends_on = None

NEW_PERMISSIONS = {
    "gps_samples:sync": "Submit transport GPS location samples",
    "gps_samples:read": "Read transport GPS location history",
}

ROLE_PERMISSIONS_DELTA = {
    "platform_super_admin": tuple(NEW_PERMISSIONS),
    "platform_support": ("gps_samples:read",),
    "school_admin": tuple(NEW_PERMISSIONS),
    "school_finance": ("gps_samples:read",),
    "teacher": (),
    "bus_attendant": ("gps_samples:sync",),
    "parent": (),
}

RLS_TABLE = "location_samples"


def upgrade() -> None:
    op.create_table(
        "location_samples",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column(
            "client_device_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("client_devices.id"),
            nullable=False,
        ),
        sa.Column("client_sample_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("trip_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("bus_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("attendant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("latitude", sa.Numeric(9, 6), nullable=False),
        sa.Column("longitude", sa.Numeric(9, 6), nullable=False),
        sa.Column("accuracy_meters", sa.Numeric(8, 2), nullable=True),
        sa.Column("altitude_meters", sa.Numeric(8, 2), nullable=True),
        sa.Column("speed_mps", sa.Numeric(8, 2), nullable=True),
        sa.Column("heading_degrees", sa.Numeric(6, 2), nullable=True),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("device_sequence", sa.BigInteger(), nullable=True),
        sa.Column("source", sa.String(32), nullable=False, server_default="phone_gnss"),
        sa.Column("processing_state", sa.String(32), nullable=False),
        sa.Column("rejection_code", sa.String(64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("client_device_id", "client_sample_id", name="uq_location_samples_device_sample"),
        sa.UniqueConstraint("id", "tenant_id", name="uq_location_samples_id_tenant"),
        sa.CheckConstraint("latitude >= -90 AND latitude <= 90", name="ck_location_samples_latitude"),
        sa.CheckConstraint("longitude >= -180 AND longitude <= 180", name="ck_location_samples_longitude"),
        sa.CheckConstraint(
            "accuracy_meters IS NULL OR accuracy_meters >= 0",
            name="ck_location_samples_accuracy",
        ),
        sa.CheckConstraint(
            "speed_mps IS NULL OR speed_mps >= 0",
            name="ck_location_samples_speed",
        ),
        sa.CheckConstraint(
            "heading_degrees IS NULL OR (heading_degrees >= 0 AND heading_degrees < 360)",
            name="ck_location_samples_heading",
        ),
        sa.CheckConstraint(
            "processing_state IN ('recorded', 'rejected')",
            name="ck_location_samples_processing_state",
        ),
        sa.CheckConstraint(
            "source IN ('phone_gnss', 'hardware_tracker')",
            name="ck_location_samples_source",
        ),
    )
    op.create_index(
        "ix_location_samples_tenant_trip_occurred",
        "location_samples",
        ["tenant_id", "trip_id", "occurred_at"],
    )
    op.create_index(
        "ix_location_samples_tenant_bus_occurred",
        "location_samples",
        ["tenant_id", "bus_id", "occurred_at"],
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
    op.execute(
        f"""
        GRANT SELECT, INSERT, UPDATE, DELETE ON {RLS_TABLE}
        TO schoolpass_app
        """
    )
    _seed_permissions()


def _seed_permissions() -> None:
    conn = op.get_bind()
    perm_ids: dict[str, object] = {}
    for code, description in NEW_PERMISSIONS.items():
        perm_id = conn.execute(
            sa.text(
                """
                INSERT INTO permissions (id, code, description)
                VALUES (gen_random_uuid(), :code, :description)
                ON CONFLICT (code) DO UPDATE SET description = EXCLUDED.description
                RETURNING id
                """
            ),
            {"code": code, "description": description},
        ).scalar_one()
        perm_ids[code] = perm_id

    role_rows = conn.execute(sa.text("SELECT id, name FROM roles WHERE is_system IS TRUE AND tenant_id IS NULL"))
    role_ids = {row.name: row.id for row in role_rows}
    for role_name, codes in ROLE_PERMISSIONS_DELTA.items():
        role_id = role_ids.get(role_name)
        if role_id is None:
            continue
        for code in codes:
            conn.execute(
                sa.text(
                    """
                    INSERT INTO role_permissions (role_id, permission_id)
                    VALUES (:rid, :pid)
                    ON CONFLICT DO NOTHING
                    """
                ),
                {"rid": role_id, "pid": perm_ids[code]},
            )


def downgrade() -> None:
    op.execute(f"DROP POLICY IF EXISTS tenant_isolation ON {RLS_TABLE}")
    op.drop_table("location_samples")
    conn = op.get_bind()
    for code in NEW_PERMISSIONS:
        conn.execute(
            sa.text(
                """
                DELETE FROM role_permissions rp
                USING permissions p
                WHERE rp.permission_id = p.id AND p.code = :code
                """
            ),
            {"code": code},
        )
        conn.execute(sa.text("DELETE FROM permissions WHERE code = :code"), {"code": code})
