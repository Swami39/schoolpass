"""RFID ingest domain.

Revision ID: 0004_rfid_ingest
Revises: 0003_card_domain
Create Date: 2026-09-19
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0004_rfid_ingest"
down_revision = "0003_card_domain"
branch_labels = None
depends_on = None

NEW_PERMISSIONS = {
    "rfid_readers:create": "Create RFID readers",
    "rfid_readers:read": "Read RFID readers",
    "rfid_readers:update": "Update RFID readers",
    "rfid_devices:create": "Register RFID devices",
    "rfid_devices:read": "Read RFID devices",
    "rfid_devices:update": "Update RFID devices",
    "rfid_devices:rotate_keys": "Rotate RFID device keys",
    "rfid_events:read": "Read RFID events",
}

ROLE_PERMISSIONS_DELTA = {
    "platform_super_admin": tuple(NEW_PERMISSIONS),
    "platform_support": ("rfid_readers:read", "rfid_devices:read", "rfid_events:read"),
    "school_admin": tuple(NEW_PERMISSIONS),
    "school_finance": ("rfid_readers:read", "rfid_devices:read", "rfid_events:read"),
    "teacher": ("rfid_readers:read", "rfid_events:read"),
    "bus_attendant": (),
    "parent": (),
}

RLS_TABLES = (
    "rfid_readers",
    "rfid_events",
    "rfid_event_processing",
    "rfid_observations",
    "rfid_ingest_rejects",
)


def upgrade() -> None:
    op.create_table(
        "rfid_readers",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("location", sa.String(255), nullable=True),
        sa.Column("gate_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("direction_mode", sa.String(32), nullable=True),
        sa.Column("status", sa.String(32), nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("id", "tenant_id", name="uq_rfid_readers_id_tenant"),
        sa.CheckConstraint("status IN ('active', 'blocked', 'retired')", name="ck_rfid_readers_status"),
    )

    # Device directory — no RLS (architecture: device_id → tenant before GUC). No student PII.
    op.create_table(
        "rfid_devices",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("device_id", sa.String(128), nullable=False, unique=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("reader_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("key_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("status", sa.String(32), nullable=False, server_default="active"),
        sa.Column("device_name", sa.String(255), nullable=True),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(
            ["reader_id", "tenant_id"],
            ["rfid_readers.id", "rfid_readers.tenant_id"],
            name="fk_rfid_devices_reader_tenant",
        ),
        sa.CheckConstraint("status IN ('active', 'blocked', 'retired')", name="ck_rfid_devices_status"),
    )
    op.create_index("ix_rfid_devices_tenant", "rfid_devices", ["tenant_id"])

    op.create_table(
        "rfid_device_keys",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("device_uuid", postgresql.UUID(as_uuid=True), sa.ForeignKey("rfid_devices.id"), nullable=False),
        sa.Column("key_version", sa.Integer(), nullable=False),
        sa.Column(
            "secret_encrypted",
            sa.Text(),
            nullable=False,
            comment="Fernet-encrypted HMAC secret; not a password hash",
        ),
        sa.Column("status", sa.String(32), nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("device_uuid", "key_version", name="uq_rfid_device_keys_device_version"),
        sa.CheckConstraint("status IN ('active', 'revoked')", name="ck_rfid_device_keys_status"),
    )

    op.create_table(
        "rfid_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("reader_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("device_uuid", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("device_event_id", sa.String(128), nullable=False),
        sa.Column("physical_card_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("assignment_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("student_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("hf_uid", sa.String(128), nullable=True),
        sa.Column("uhf_epc", sa.String(128), nullable=True),
        sa.Column("uhf_tid", sa.String(128), nullable=True),
        sa.Column("antenna", sa.Integer(), nullable=True),
        sa.Column("rssi", sa.Numeric(8, 2), nullable=True),
        sa.Column("direction", sa.String(32), nullable=True),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("signature_key_version", sa.Integer(), nullable=False),
        sa.Column("ingest_status", sa.String(32), nullable=False, server_default="accepted"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(
            ["reader_id", "tenant_id"],
            ["rfid_readers.id", "rfid_readers.tenant_id"],
            name="fk_rfid_events_reader_tenant",
        ),
        sa.ForeignKeyConstraint(
            ["device_uuid"],
            ["rfid_devices.id"],
            name="fk_rfid_events_device",
        ),
        sa.ForeignKeyConstraint(
            ["physical_card_id", "tenant_id"],
            ["physical_cards.id", "physical_cards.tenant_id"],
            name="fk_rfid_events_card_tenant",
        ),
        sa.ForeignKeyConstraint(
            ["assignment_id", "tenant_id"],
            ["card_assignments.id", "card_assignments.tenant_id"],
            name="fk_rfid_events_assignment_tenant",
        ),
        sa.ForeignKeyConstraint(
            ["student_id", "tenant_id"],
            ["students.id", "students.tenant_id"],
            name="fk_rfid_events_student_tenant",
        ),
        sa.UniqueConstraint("id", "tenant_id", name="uq_rfid_events_id_tenant"),
        sa.UniqueConstraint("tenant_id", "reader_id", "device_event_id", name="uq_rfid_events_idempotency"),
    )
    op.create_index("ix_rfid_events_tenant_received", "rfid_events", ["tenant_id", "received_at"])
    op.create_index("ix_rfid_events_tenant_epc", "rfid_events", ["tenant_id", "uhf_epc"])

    op.create_table(
        "rfid_event_processing",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("rfid_event_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="pending"),
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_error_code", sa.String(64), nullable=True),
        sa.Column("last_error_message", sa.String(255), nullable=True),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(
            ["rfid_event_id", "tenant_id"],
            ["rfid_events.id", "rfid_events.tenant_id"],
            name="fk_rfid_processing_event_tenant",
        ),
        sa.UniqueConstraint("rfid_event_id", name="uq_rfid_event_processing_event"),
        sa.UniqueConstraint("id", "tenant_id", name="uq_rfid_event_processing_id_tenant"),
        sa.CheckConstraint(
            "status IN ('pending', 'processing', 'processed', 'rejected', 'failed')",
            name="ck_rfid_event_processing_status",
        ),
    )

    op.create_table(
        "rfid_observations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("rfid_event_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("physical_card_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("assignment_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("student_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("resolution_status", sa.String(32), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(
            ["rfid_event_id", "tenant_id"],
            ["rfid_events.id", "rfid_events.tenant_id"],
            name="fk_rfid_observations_event_tenant",
        ),
        sa.UniqueConstraint("rfid_event_id", name="uq_rfid_observations_event"),
        sa.UniqueConstraint("id", "tenant_id", name="uq_rfid_observations_id_tenant"),
    )

    op.create_table(
        "rfid_ingest_rejects",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("device_external_id", sa.String(128), nullable=True),
        sa.Column("reader_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("reason_code", sa.String(64), nullable=False),
        sa.Column("correlation_id", sa.String(64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("id", name="pk_rfid_ingest_rejects"),
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
        GRANT SELECT, INSERT, UPDATE ON rfid_devices, rfid_device_keys TO schoolpass_app
        """
    )
    op.execute(
        """
        GRANT SELECT, INSERT, UPDATE, DELETE ON
          rfid_readers, rfid_events, rfid_event_processing, rfid_observations, rfid_ingest_rejects
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
    op.drop_table("rfid_ingest_rejects")
    op.drop_table("rfid_observations")
    op.drop_table("rfid_event_processing")
    op.drop_table("rfid_events")
    op.drop_table("rfid_readers")
    op.drop_table("rfid_device_keys")
    op.drop_table("rfid_devices")
