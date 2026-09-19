"""Teacher assignments, timetable, results, and teacher app permissions (Phase 9).

Revision ID: 0015_teacher_domain
Revises: 0014_notify_prefs
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0015_teacher_domain"
down_revision = "0014_notify_prefs"
branch_labels = None
depends_on = None

RLS_TABLES = (
    "subjects",
    "teacher_section_assignments",
    "timetable_periods",
    "assessments",
    "student_assessment_marks",
    "teacher_class_nfc_events",
    "teacher_messages",
)

NEW_PERMISSIONS = {
    "teacher:me_read": "Read authenticated teacher profile",
    "teacher:classes_read": "List teacher class assignments",
    "teacher:students_read": "List students in assigned classes",
    "teacher:attendance_read": "Read attendance for assigned classes",
    "teacher:attendance_write": "Mark or correct attendance for assigned classes",
    "teacher:nfc_attendance": "Submit class NFC attendance events",
    "teacher:timetable_read": "Read teacher timetable",
    "teacher:timetable_write": "Update teacher timetable where authorized",
    "teacher:results_read": "Read results for assigned classes",
    "teacher:results_write": "Enter or update results for assigned classes",
    "teacher:messages_write": "Send messages to parents of authorized students",
    "teacher:notifications_read": "Read teacher notification inbox",
}

TEACHER_ROLE_PERMISSIONS = tuple(NEW_PERMISSIONS.keys())


def _enable_rls(table: str) -> None:
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
    op.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON {table} TO schoolpass_app")


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
    teacher_role = role_ids.get("teacher")
    super_admin = role_ids.get("platform_super_admin")
    for role in (teacher_role, super_admin):
        if role is None:
            continue
        for code in TEACHER_ROLE_PERMISSIONS:
            conn.execute(
                sa.text(
                    """
                    INSERT INTO role_permissions (role_id, permission_id)
                    VALUES (:rid, :pid)
                    ON CONFLICT DO NOTHING
                    """
                ),
                {"rid": role, "pid": perm_ids[code]},
            )


def upgrade() -> None:
    op.create_table(
        "subjects",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("code", sa.String(32), nullable=False),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("id", "tenant_id", name="uq_subjects_id_tenant"),
        sa.UniqueConstraint("tenant_id", "code", name="uq_subjects_tenant_code"),
        sa.CheckConstraint("status IN ('active', 'inactive')", name="ck_subjects_status"),
    )
    op.create_table(
        "teacher_section_assignments",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("teacher_user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("academic_year_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("section_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("subject_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("assignment_role", sa.String(32), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(
            ["academic_year_id", "tenant_id"],
            ["academic_years.id", "academic_years.tenant_id"],
            name="fk_teacher_assign_year_tenant",
        ),
        sa.ForeignKeyConstraint(
            ["section_id", "tenant_id"],
            ["sections.id", "sections.tenant_id"],
            name="fk_teacher_assign_section_tenant",
        ),
        sa.ForeignKeyConstraint(
            ["subject_id", "tenant_id"],
            ["subjects.id", "subjects.tenant_id"],
            name="fk_teacher_assign_subject_tenant",
        ),
        sa.ForeignKeyConstraint(
            ["teacher_user_id", "tenant_id"],
            ["staff_profiles.user_id", "staff_profiles.tenant_id"],
            name="fk_teacher_assign_staff_tenant",
        ),
        sa.UniqueConstraint("id", "tenant_id", name="uq_teacher_section_assignments_id_tenant"),
        sa.UniqueConstraint(
            "tenant_id",
            "teacher_user_id",
            "academic_year_id",
            "section_id",
            "subject_id",
            name="uq_teacher_section_assignments_teacher_section_subject",
        ),
        sa.CheckConstraint(
            "assignment_role IN ('class_teacher', 'subject_teacher')",
            name="ck_teacher_section_assignments_role",
        ),
        sa.CheckConstraint("status IN ('active', 'inactive')", name="ck_teacher_section_assignments_status"),
    )
    op.create_table(
        "timetable_periods",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("academic_year_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("section_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("day_of_week", sa.Integer(), nullable=False),
        sa.Column("period_number", sa.Integer(), nullable=False),
        sa.Column("starts_at", sa.Time(), nullable=False),
        sa.Column("ends_at", sa.Time(), nullable=False),
        sa.Column("subject_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("teacher_user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(
            ["academic_year_id", "tenant_id"],
            ["academic_years.id", "academic_years.tenant_id"],
            name="fk_timetable_year_tenant",
        ),
        sa.ForeignKeyConstraint(
            ["section_id", "tenant_id"],
            ["sections.id", "sections.tenant_id"],
            name="fk_timetable_section_tenant",
        ),
        sa.ForeignKeyConstraint(
            ["subject_id", "tenant_id"],
            ["subjects.id", "subjects.tenant_id"],
            name="fk_timetable_subject_tenant",
        ),
        sa.ForeignKeyConstraint(
            ["teacher_user_id", "tenant_id"],
            ["staff_profiles.user_id", "staff_profiles.tenant_id"],
            name="fk_timetable_teacher_tenant",
        ),
        sa.UniqueConstraint("id", "tenant_id", name="uq_timetable_periods_id_tenant"),
        sa.UniqueConstraint(
            "tenant_id",
            "academic_year_id",
            "section_id",
            "day_of_week",
            "period_number",
            name="uq_timetable_period_slot",
        ),
        sa.CheckConstraint("day_of_week BETWEEN 0 AND 6", name="ck_timetable_day_of_week"),
        sa.CheckConstraint("period_number > 0", name="ck_timetable_period_number"),
    )
    op.create_table(
        "assessments",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("academic_year_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("section_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("subject_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("code", sa.String(64), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("max_marks", sa.Integer(), nullable=False),
        sa.Column("scheduled_on", sa.Date(), nullable=True),
        sa.Column("status", sa.String(32), nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(
            ["academic_year_id", "tenant_id"],
            ["academic_years.id", "academic_years.tenant_id"],
            name="fk_assessments_year_tenant",
        ),
        sa.ForeignKeyConstraint(
            ["section_id", "tenant_id"],
            ["sections.id", "sections.tenant_id"],
            name="fk_assessments_section_tenant",
        ),
        sa.ForeignKeyConstraint(
            ["subject_id", "tenant_id"],
            ["subjects.id", "subjects.tenant_id"],
            name="fk_assessments_subject_tenant",
        ),
        sa.UniqueConstraint("id", "tenant_id", name="uq_assessments_id_tenant"),
        sa.UniqueConstraint(
            "tenant_id",
            "academic_year_id",
            "section_id",
            "subject_id",
            "code",
            name="uq_assessments_section_subject_code",
        ),
        sa.CheckConstraint("max_marks > 0", name="ck_assessments_max_marks"),
        sa.CheckConstraint("status IN ('active', 'archived')", name="ck_assessments_status"),
    )
    op.create_table(
        "student_assessment_marks",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("assessment_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("student_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("marks", sa.Integer(), nullable=False),
        sa.Column("entered_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(
            ["assessment_id", "tenant_id"],
            ["assessments.id", "assessments.tenant_id"],
            name="fk_student_marks_assessment_tenant",
        ),
        sa.ForeignKeyConstraint(
            ["student_id", "tenant_id"],
            ["students.id", "students.tenant_id"],
            name="fk_student_marks_student_tenant",
        ),
        sa.UniqueConstraint("id", "tenant_id", name="uq_student_assessment_marks_id_tenant"),
        sa.UniqueConstraint(
            "tenant_id",
            "assessment_id",
            "student_id",
            name="uq_student_assessment_marks_student_assessment",
        ),
        sa.CheckConstraint("marks >= 0", name="ck_student_assessment_marks_nonneg"),
    )
    op.create_table(
        "teacher_class_nfc_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("client_device_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("client_event_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("teacher_user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("section_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("card_hf_uid", sa.String(64), nullable=False),
        sa.Column("student_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("attendance_record_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("processing_state", sa.String(64), nullable=False),
        sa.Column("rejection_code", sa.String(64), nullable=True),
        sa.Column("device_sequence", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(
            ["section_id", "tenant_id"],
            ["sections.id", "sections.tenant_id"],
            name="fk_teacher_nfc_section_tenant",
        ),
        sa.UniqueConstraint("client_device_id", "client_event_id", name="uq_teacher_nfc_device_event"),
        sa.UniqueConstraint("id", "tenant_id", name="uq_teacher_class_nfc_events_id_tenant"),
    )
    op.create_table(
        "teacher_messages",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("teacher_user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("section_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("student_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("urgent", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("image_file_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("idempotency_key", sa.String(256), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(
            ["image_file_id", "tenant_id"],
            ["files.id", "files.tenant_id"],
            name="fk_teacher_messages_file_tenant",
        ),
        sa.UniqueConstraint("tenant_id", "idempotency_key", name="uq_teacher_messages_idempotency"),
        sa.UniqueConstraint("id", "tenant_id", name="uq_teacher_messages_id_tenant"),
    )
    for table in RLS_TABLES:
        _enable_rls(table)
    _seed_permissions()


def downgrade() -> None:
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
    for table in reversed(RLS_TABLES):
        op.execute(f"DROP POLICY IF EXISTS tenant_isolation ON {table}")
        op.drop_table(table)
