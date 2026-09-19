"""Attendance domain derived from RFID observations.

Revision ID: 0005_attendance
Revises: 0004_rfid_ingest
Create Date: 2026-09-19
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0005_attendance"
down_revision = "0004_rfid_ingest"
branch_labels = None
depends_on = None

NEW_PERMISSIONS = {
    "attendance:read": "Read attendance records",
    "attendance:create": "Create attendance records",
    "attendance:update": "Update attendance records",
    "attendance:correct": "Correct attendance records",
    "attendance:finalize": "Finalize daily attendance",
    "attendance:manage_policy": "Manage attendance policies",
}

ROLE_PERMISSIONS_DELTA = {
    "platform_super_admin": tuple(NEW_PERMISSIONS),
    "platform_support": ("attendance:read",),
    "school_admin": tuple(NEW_PERMISSIONS),
    "school_finance": ("attendance:read",),
    "teacher": ("attendance:read",),
    "bus_attendant": (),
    "parent": (),
}

RLS_TABLES = (
    "attendance_policies",
    "attendance_non_school_days",
    "attendance_signals",
    "attendance_records",
    "attendance_corrections",
    "attendance_daily_runs",
    "attendance_observation_processing",
)


def upgrade() -> None:
    op.create_table(
        "attendance_policies",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("effective_from", sa.Date(), nullable=False),
        sa.Column("effective_to", sa.Date(), nullable=True),
        sa.Column("entry_start_time", sa.Time(), nullable=True),
        sa.Column("present_until", sa.Time(), nullable=True),
        sa.Column("late_until", sa.Time(), nullable=True),
        sa.Column("entry_dedupe_seconds", sa.Integer(), nullable=False, server_default="30"),
        sa.Column("exit_dedupe_seconds", sa.Integer(), nullable=False, server_default="30"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("id", "tenant_id", name="uq_attendance_policies_id_tenant"),
    )

    op.create_table(
        "attendance_non_school_days",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("on_date", sa.Date(), nullable=False),
        sa.Column("reason", sa.String(255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("tenant_id", "on_date", name="uq_attendance_non_school_days_tenant_date"),
        sa.UniqueConstraint("id", "tenant_id", name="uq_attendance_non_school_days_id_tenant"),
    )

    op.create_table(
        "attendance_signals",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("student_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("rfid_observation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("attendance_date", sa.Date(), nullable=False),
        sa.Column("direction", sa.String(16), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("dedupe_key", sa.String(255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(
            ["student_id", "tenant_id"],
            ["students.id", "students.tenant_id"],
            name="fk_attendance_signals_student_tenant",
        ),
        sa.ForeignKeyConstraint(
            ["rfid_observation_id", "tenant_id"],
            ["rfid_observations.id", "rfid_observations.tenant_id"],
            name="fk_attendance_signals_observation_tenant",
        ),
        sa.UniqueConstraint("tenant_id", "dedupe_key", name="uq_attendance_signals_dedupe"),
        sa.UniqueConstraint("tenant_id", "rfid_observation_id", name="uq_attendance_signals_observation"),
        sa.UniqueConstraint("id", "tenant_id", name="uq_attendance_signals_id_tenant"),
        sa.CheckConstraint("direction IN ('entry', 'exit')", name="ck_attendance_signals_direction"),
    )
    op.create_index(
        "ix_attendance_signals_tenant_student_date",
        "attendance_signals",
        ["tenant_id", "student_id", "attendance_date", "direction"],
    )

    op.create_table(
        "attendance_records",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("student_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("academic_year_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("attendance_date", sa.Date(), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("entry_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("exit_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("first_observation_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("last_observation_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("source", sa.String(32), nullable=False, server_default="rfid"),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(
            ["student_id", "tenant_id"],
            ["students.id", "students.tenant_id"],
            name="fk_attendance_records_student_tenant",
        ),
        sa.ForeignKeyConstraint(
            ["academic_year_id", "tenant_id"],
            ["academic_years.id", "academic_years.tenant_id"],
            name="fk_attendance_records_year_tenant",
        ),
        sa.UniqueConstraint("tenant_id", "student_id", "attendance_date", name="uq_attendance_records_student_date"),
        sa.UniqueConstraint("id", "tenant_id", name="uq_attendance_records_id_tenant"),
        sa.CheckConstraint(
            "status IN ('present', 'late', 'absent', 'excused', 'corrected')",
            name="ck_attendance_records_status",
        ),
    )
    op.create_index(
        "ix_attendance_records_tenant_date",
        "attendance_records",
        ["tenant_id", "attendance_date", "student_id"],
    )

    op.create_table(
        "attendance_corrections",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("attendance_record_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("previous_status", sa.String(32), nullable=True),
        sa.Column("new_status", sa.String(32), nullable=False),
        sa.Column("previous_entry_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("new_entry_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("previous_exit_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("new_exit_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("corrected_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(
            ["attendance_record_id", "tenant_id"],
            ["attendance_records.id", "attendance_records.tenant_id"],
            name="fk_attendance_corrections_record_tenant",
        ),
        sa.UniqueConstraint("id", "tenant_id", name="uq_attendance_corrections_id_tenant"),
    )

    op.create_table(
        "attendance_daily_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("attendance_date", sa.Date(), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("tenant_id", "attendance_date", name="uq_attendance_daily_runs_tenant_date"),
        sa.UniqueConstraint("id", "tenant_id", name="uq_attendance_daily_runs_id_tenant"),
        sa.CheckConstraint("status IN ('running', 'completed', 'failed')", name="ck_attendance_daily_runs_status"),
    )

    op.create_table(
        "attendance_observation_processing",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("rfid_observation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="pending"),
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_error_code", sa.String(64), nullable=True),
        sa.Column("last_error_message", sa.String(255), nullable=True),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(
            ["rfid_observation_id", "tenant_id"],
            ["rfid_observations.id", "rfid_observations.tenant_id"],
            name="fk_attendance_obs_proc_observation_tenant",
        ),
        sa.UniqueConstraint("rfid_observation_id", name="uq_attendance_observation_processing_obs"),
        sa.UniqueConstraint("id", "tenant_id", name="uq_attendance_observation_processing_id_tenant"),
        sa.CheckConstraint(
            "status IN ('pending', 'processing', 'processed', 'rejected', 'failed')",
            name="ck_attendance_observation_processing_status",
        ),
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
        GRANT SELECT, INSERT, UPDATE, DELETE ON
          attendance_policies,
          attendance_non_school_days,
          attendance_signals,
          attendance_records,
          attendance_corrections,
          attendance_daily_runs,
          attendance_observation_processing
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
    op.drop_table("attendance_observation_processing")
    op.drop_table("attendance_daily_runs")
    op.drop_table("attendance_corrections")
    op.drop_table("attendance_records")
    op.drop_table("attendance_signals")
    op.drop_table("attendance_non_school_days")
    op.drop_table("attendance_policies")
