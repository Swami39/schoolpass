"""Transport NFC attendance — client events and boarding records.

Revision ID: 0008_transport_nfc_attendance
Revises: 0007_transport_trip_hardening
Create Date: 2026-09-19
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0008_transport_nfc_attendance"
down_revision = "0007_transport_trip_hardening"
branch_labels = None
depends_on = None

NEW_PERMISSIONS = {
    "transport_nfc:sync": "Submit transport NFC client events",
    "transport_boarding:read": "Read transport boarding records",
}

ROLE_PERMISSIONS_DELTA = {
    "platform_super_admin": tuple(NEW_PERMISSIONS),
    "platform_support": ("transport_boarding:read",),
    "school_admin": tuple(NEW_PERMISSIONS),
    "school_finance": ("transport_boarding:read",),
    "teacher": (),
    "bus_attendant": ("transport_nfc:sync", "transport_boarding:read"),
    "parent": (),
}

RLS_TABLES = ("client_events", "transport_boarding_records")


def upgrade() -> None:
    op.create_table(
        "client_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column(
            "client_device_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("client_devices.id"),
            nullable=False,
        ),
        sa.Column("client_event_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("actor_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("event_type", sa.String(32), nullable=False),
        sa.Column("card_uid", sa.String(128), nullable=False),
        sa.Column("trip_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("trip_stop_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("device_sequence", sa.BigInteger(), nullable=True),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("sync_attempts", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("processing_state", sa.String(64), nullable=False),
        sa.Column("rejection_code", sa.String(64), nullable=True),
        sa.Column(
            "transport_boarding_record_id",
            postgresql.UUID(as_uuid=True),
            nullable=True,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("client_device_id", "client_event_id", name="uq_client_events_device_event"),
        sa.UniqueConstraint("id", "tenant_id", name="uq_client_events_id_tenant"),
        sa.CheckConstraint("event_type IN ('boarding', 'dropoff')", name="ck_client_events_event_type"),
        sa.CheckConstraint("sync_attempts >= 1", name="ck_client_events_sync_attempts"),
    )
    op.create_index("ix_client_events_tenant_received", "client_events", ["tenant_id", "received_at"])
    op.create_index("ix_client_events_tenant_trip", "client_events", ["tenant_id", "trip_id"])

    op.create_table(
        "transport_boarding_records",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("trip_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("bus_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("attendant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("student_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("transport_assignment_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("card_assignment_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("physical_card_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("client_event_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("event_type", sa.String(32), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("trip_stop_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("source", sa.String(32), nullable=False, server_default="nfc"),
        sa.Column("status", sa.String(32), nullable=False, server_default="recorded"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(
            ["trip_id", "tenant_id"],
            ["trips.id", "trips.tenant_id"],
            name="fk_transport_boarding_trip_tenant",
        ),
        sa.ForeignKeyConstraint(
            ["bus_id", "tenant_id"],
            ["buses.id", "buses.tenant_id"],
            name="fk_transport_boarding_bus_tenant",
        ),
        sa.ForeignKeyConstraint(
            ["attendant_id", "tenant_id"],
            ["transport_attendants.id", "transport_attendants.tenant_id"],
            name="fk_transport_boarding_attendant_tenant",
        ),
        sa.ForeignKeyConstraint(
            ["student_id", "tenant_id"],
            ["students.id", "students.tenant_id"],
            name="fk_transport_boarding_student_tenant",
        ),
        sa.ForeignKeyConstraint(
            ["transport_assignment_id", "tenant_id"],
            ["transport_assignments.id", "transport_assignments.tenant_id"],
            name="fk_transport_boarding_assignment_tenant",
        ),
        sa.ForeignKeyConstraint(
            ["card_assignment_id", "tenant_id"],
            ["card_assignments.id", "card_assignments.tenant_id"],
            name="fk_transport_boarding_card_assignment_tenant",
        ),
        sa.ForeignKeyConstraint(
            ["physical_card_id", "tenant_id"],
            ["physical_cards.id", "physical_cards.tenant_id"],
            name="fk_transport_boarding_card_tenant",
        ),
        sa.ForeignKeyConstraint(
            ["client_event_id", "tenant_id"],
            ["client_events.id", "client_events.tenant_id"],
            name="fk_transport_boarding_client_event_tenant",
        ),
        sa.ForeignKeyConstraint(
            ["trip_stop_id", "tenant_id"],
            ["trip_stops.id", "trip_stops.tenant_id"],
            name="fk_transport_boarding_trip_stop_tenant",
        ),
        sa.UniqueConstraint("id", "tenant_id", name="uq_transport_boarding_id_tenant"),
        sa.UniqueConstraint("client_event_id", name="uq_transport_boarding_client_event"),
        sa.CheckConstraint("event_type IN ('boarding', 'dropoff')", name="ck_transport_boarding_event_type"),
        sa.CheckConstraint("source IN ('nfc')", name="ck_transport_boarding_source"),
        sa.CheckConstraint("status IN ('recorded')", name="ck_transport_boarding_status"),
    )
    op.create_index(
        "ix_transport_boarding_tenant_occurred",
        "transport_boarding_records",
        ["tenant_id", "occurred_at"],
    )
    op.create_index(
        "ix_transport_boarding_tenant_trip",
        "transport_boarding_records",
        ["tenant_id", "trip_id"],
    )

    op.execute(
        """
        ALTER TABLE client_events
        ADD CONSTRAINT fk_client_events_boarding_record_tenant
        FOREIGN KEY (transport_boarding_record_id, tenant_id)
        REFERENCES transport_boarding_records (id, tenant_id)
        """
    )

    for table in RLS_TABLES:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        op.execute(
            f"""
            CREATE POLICY tenant_isolation ON {table}
              USING (
                tenant_id IS NOT DISTINCT FROM NULLIF(current_setting('app.tenant_id', true), '')::uuid
              )
              WITH CHECK (
                tenant_id IS NOT DISTINCT FROM NULLIF(current_setting('app.tenant_id', true), '')::uuid
              )
            """
        )

    op.execute(
        """
        GRANT SELECT, INSERT, UPDATE, DELETE ON client_events, transport_boarding_records
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
    for table in reversed(RLS_TABLES):
        op.execute(f"DROP POLICY IF EXISTS tenant_isolation ON {table}")
    op.execute("ALTER TABLE client_events DROP CONSTRAINT IF EXISTS fk_client_events_boarding_record_tenant")
    op.drop_table("transport_boarding_records")
    op.drop_table("client_events")
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
