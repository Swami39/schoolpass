"""Student, guardian, enrollment, and academic structure domain.

Revision ID: 0002_student_domain
Revises: 0001_foundation
Create Date: 2026-09-19
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0002_student_domain"
down_revision = "0001_foundation"
branch_labels = None
depends_on = None

NEW_PERMISSIONS = {
    "students:read": "Read students",
    "students:create": "Create students",
    "students:update": "Update students",
    "students:withdraw": "Withdraw students",
    "students:hide": "Hide student PII from operational views",
    "students:anonymize": "Anonymize student PII",
    "guardians:read": "Read guardians",
    "guardians:create": "Create guardians",
    "guardians:update": "Update guardians",
    "student_guardians:read": "Read student-guardian links",
    "student_guardians:write": "Manage student-guardian links",
    "enrollments:read": "Read enrollments",
    "enrollments:create": "Create enrollments",
    "enrollments:update": "Update enrollments",
    "academic:read": "Read classes, sections, and academic years",
    "academic:write": "Manage classes, sections, and academic years",
    "files:read": "Read file metadata",
    "files:write": "Create file metadata records",
}

ROLE_PERMISSIONS_DELTA = {
    "platform_super_admin": tuple(NEW_PERMISSIONS),
    "platform_support": ("students:read", "guardians:read", "enrollments:read", "academic:read"),
    "school_admin": (
        "students:read",
        "students:create",
        "students:update",
        "students:withdraw",
        "students:hide",
        "students:anonymize",
        "guardians:read",
        "guardians:create",
        "guardians:update",
        "student_guardians:read",
        "student_guardians:write",
        "enrollments:read",
        "enrollments:create",
        "enrollments:update",
        "academic:read",
        "academic:write",
        "files:read",
        "files:write",
    ),
    "school_finance": ("students:read", "guardians:read", "enrollments:read", "academic:read"),
    "teacher": ("students:read", "enrollments:read", "academic:read", "student_guardians:read"),
    "bus_attendant": ("students:read",),
    "parent": ("students:read", "guardians:read", "enrollments:read"),
}

TENANT_TABLES = (
    "files",
    "academic_years",
    "classes",
    "sections",
    "students",
    "guardians",
    "student_guardians",
    "enrollments",
)


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")

    op.create_table(
        "files",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("purpose", sa.String(64), nullable=False),
        sa.Column("blob_key", sa.String(512), nullable=False),
        sa.Column("sha256", sa.String(64), nullable=True),
        sa.Column("classification", sa.String(64), nullable=False, server_default="SENSITIVE_CHILD_DATA"),
        sa.Column("status", sa.String(32), nullable=False, server_default="active"),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("id", "tenant_id", name="uq_files_id_tenant"),
        sa.UniqueConstraint("tenant_id", "blob_key", name="uq_files_tenant_blob_key"),
    )

    op.create_table(
        "academic_years",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("code", sa.String(32), nullable=False),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("starts_on", sa.Date(), nullable=False),
        sa.Column("ends_on", sa.Date(), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("id", "tenant_id", name="uq_academic_years_id_tenant"),
        sa.UniqueConstraint("tenant_id", "code", name="uq_academic_years_tenant_code"),
        sa.CheckConstraint("ends_on >= starts_on", name="ck_academic_years_dates"),
    )

    op.create_table(
        "classes",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("code", sa.String(32), nullable=False),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("id", "tenant_id", name="uq_classes_id_tenant"),
        sa.UniqueConstraint("tenant_id", "code", name="uq_classes_tenant_code"),
    )

    op.create_table(
        "sections",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("class_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(32), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(
            ["class_id", "tenant_id"],
            ["classes.id", "classes.tenant_id"],
            name="fk_sections_class_tenant",
        ),
        sa.UniqueConstraint("id", "tenant_id", name="uq_sections_id_tenant"),
        sa.UniqueConstraint("tenant_id", "class_id", "name", name="uq_sections_tenant_class_name"),
    )

    op.create_table(
        "students",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("historical_subject_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("admission_no", sa.String(64), nullable=False),
        sa.Column("first_name", sa.String(128), nullable=False),
        sa.Column("middle_name", sa.String(128), nullable=True),
        sa.Column("last_name", sa.String(128), nullable=False),
        sa.Column("date_of_birth", sa.Date(), nullable=True),
        sa.Column("photo_file_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("status", sa.String(32), nullable=False, server_default="active"),
        sa.Column("pii_state", sa.String(32), nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(
            ["photo_file_id", "tenant_id"],
            ["files.id", "files.tenant_id"],
            name="fk_students_photo_file_tenant",
        ),
        sa.UniqueConstraint("id", "tenant_id", name="uq_students_id_tenant"),
        sa.UniqueConstraint("historical_subject_id", name="uq_students_historical_subject_id"),
        sa.UniqueConstraint("tenant_id", "admission_no", name="uq_students_tenant_admission_no"),
        sa.CheckConstraint("status IN ('active', 'withdrawn')", name="ck_students_status"),
        sa.CheckConstraint("pii_state IN ('active', 'hidden', 'anonymized')", name="ck_students_pii_state"),
    )
    op.create_index("ix_students_tenant_status", "students", ["tenant_id", "status"])
    op.execute(
        """
        CREATE INDEX ix_students_name_trgm ON students
        USING gin (
          (first_name || ' ' || coalesce(middle_name, '') || ' ' || last_name) gin_trgm_ops
        )
        """
    )

    op.create_table(
        "guardians",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("first_name", sa.String(128), nullable=False),
        sa.Column("last_name", sa.String(128), nullable=False),
        sa.Column("phone_e164", sa.String(20), nullable=True),
        sa.Column("email", postgresql.CITEXT(), nullable=True),
        sa.Column("status", sa.String(32), nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("id", "tenant_id", name="uq_guardians_id_tenant"),
        sa.CheckConstraint("status IN ('active', 'inactive')", name="ck_guardians_status"),
    )
    op.create_index("ix_guardians_tenant_phone", "guardians", ["tenant_id", "phone_e164"])

    op.create_table(
        "student_guardians",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("student_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("guardian_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("relationship_type", sa.String(32), nullable=False),
        sa.Column("is_primary_contact", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("can_receive_notifications", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("can_pay_fees", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("status", sa.String(32), nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(
            ["student_id", "tenant_id"],
            ["students.id", "students.tenant_id"],
            name="fk_student_guardians_student_tenant",
        ),
        sa.ForeignKeyConstraint(
            ["guardian_id", "tenant_id"],
            ["guardians.id", "guardians.tenant_id"],
            name="fk_student_guardians_guardian_tenant",
        ),
        sa.UniqueConstraint("tenant_id", "student_id", "guardian_id", name="uq_student_guardians_pair"),
        sa.CheckConstraint("status IN ('active', 'inactive')", name="ck_student_guardians_status"),
    )

    op.create_table(
        "enrollments",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("student_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("academic_year_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("class_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("section_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="active"),
        sa.Column("starts_on", sa.Date(), nullable=False),
        sa.Column("ends_on", sa.Date(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(
            ["student_id", "tenant_id"],
            ["students.id", "students.tenant_id"],
            name="fk_enrollments_student_tenant",
        ),
        sa.ForeignKeyConstraint(
            ["academic_year_id", "tenant_id"],
            ["academic_years.id", "academic_years.tenant_id"],
            name="fk_enrollments_year_tenant",
        ),
        sa.ForeignKeyConstraint(
            ["class_id", "tenant_id"],
            ["classes.id", "classes.tenant_id"],
            name="fk_enrollments_class_tenant",
        ),
        sa.ForeignKeyConstraint(
            ["section_id", "tenant_id"],
            ["sections.id", "sections.tenant_id"],
            name="fk_enrollments_section_tenant",
        ),
        sa.UniqueConstraint("id", "tenant_id", name="uq_enrollments_id_tenant"),
        sa.CheckConstraint("status IN ('active', 'completed', 'withdrawn')", name="ck_enrollments_status"),
        sa.CheckConstraint("ends_on IS NULL OR ends_on >= starts_on", name="ck_enrollments_dates"),
    )
    op.create_index("ix_enrollments_student_dates", "enrollments", ["tenant_id", "student_id", "starts_on"])
    op.execute(
        """
        CREATE UNIQUE INDEX uq_enrollments_one_active_per_student
        ON enrollments (tenant_id, student_id)
        WHERE status = 'active' AND ends_on IS NULL
        """
    )

    _enable_rls()
    _grants()
    _seed_permissions()


def _tenant_policy(table: str) -> None:
    op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
    op.execute(
        f"""
        CREATE POLICY tenant_isolation ON {table}
          USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
          WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
        """
    )


def _enable_rls() -> None:
    for table in TENANT_TABLES:
        _tenant_policy(table)


def _grants() -> None:
    tables = ", ".join(TENANT_TABLES)
    op.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON {tables} TO schoolpass_app")


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
    for table in reversed(TENANT_TABLES):
        op.execute(f"DROP POLICY IF EXISTS tenant_isolation ON {table}")
        op.drop_table(table)
