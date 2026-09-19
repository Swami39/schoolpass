"""Physical cards and card assignments.

Revision ID: 0003_card_domain
Revises: 0002_student_domain
Create Date: 2026-09-19
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0003_card_domain"
down_revision = "0002_student_domain"
branch_labels = None
depends_on = None

NEW_PERMISSIONS = {
    "cards:read": "Read physical cards",
    "cards:create": "Register physical cards",
    "cards:update": "Update card metadata",
    "cards:block": "Block physical cards",
    "cards:retire": "Retire physical cards",
    "card_assignments:read": "Read card assignments",
    "card_assignments:create": "Create card assignments",
    "card_assignments:activate": "Activate card assignments",
    "card_assignments:block": "Block card assignments",
    "card_assignments:lost": "Mark card assignments lost",
    "card_assignments:revoke": "Revoke card assignments",
    "card_assignments:replace": "Replace student cards",
}

ROLE_PERMISSIONS_DELTA = {
    "platform_super_admin": tuple(NEW_PERMISSIONS),
    "platform_support": ("cards:read", "card_assignments:read"),
    "school_admin": tuple(NEW_PERMISSIONS),
    "school_finance": ("cards:read", "card_assignments:read"),
    "teacher": ("cards:read", "card_assignments:read"),
    "bus_attendant": ("cards:read", "card_assignments:read"),
    "parent": (),
}

TENANT_TABLES = ("physical_cards", "card_assignments")

ACTIVE_ASSIGNMENT_PREDICATE = (
    "status = 'active' AND revoked_at IS NULL AND activated_at IS NOT NULL"
)


def upgrade() -> None:
    op.create_table(
        "physical_cards",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("hf_uid", sa.String(128), nullable=True),
        sa.Column("uhf_epc", sa.String(128), nullable=True),
        sa.Column("uhf_tid", sa.String(128), nullable=True),
        sa.Column("profile", sa.String(32), nullable=False, server_default="uid_only"),
        sa.Column("status", sa.String(32), nullable=False, server_default="inventory"),
        sa.Column("manufactured_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("id", "tenant_id", name="uq_physical_cards_id_tenant"),
        sa.CheckConstraint(
            "profile IN ('uid_only', 'ntag_sig', 'desfire')",
            name="ck_physical_cards_profile",
        ),
        sa.CheckConstraint(
            "status IN ('inventory', 'active', 'blocked', 'retired')",
            name="ck_physical_cards_status",
        ),
    )
    op.create_index("ix_physical_cards_tenant_status", "physical_cards", ["tenant_id", "status"])
    op.execute(
        """
        CREATE UNIQUE INDEX uq_physical_cards_tenant_hf_uid
        ON physical_cards (tenant_id, hf_uid)
        WHERE hf_uid IS NOT NULL AND status != 'retired'
        """
    )
    op.execute(
        """
        CREATE UNIQUE INDEX uq_physical_cards_tenant_uhf_epc
        ON physical_cards (tenant_id, uhf_epc)
        WHERE uhf_epc IS NOT NULL AND status != 'retired'
        """
    )
    op.execute(
        """
        CREATE UNIQUE INDEX uq_physical_cards_tenant_uhf_tid
        ON physical_cards (tenant_id, uhf_tid)
        WHERE uhf_tid IS NOT NULL AND status != 'retired'
        """
    )

    op.create_table(
        "card_assignments",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("student_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("physical_card_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="pending"),
        sa.Column("issued_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("activated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoke_reason", sa.Text(), nullable=True),
        sa.Column("replaced_by_assignment_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(
            ["student_id", "tenant_id"],
            ["students.id", "students.tenant_id"],
            name="fk_card_assignments_student_tenant",
        ),
        sa.ForeignKeyConstraint(
            ["physical_card_id", "tenant_id"],
            ["physical_cards.id", "physical_cards.tenant_id"],
            name="fk_card_assignments_card_tenant",
        ),
        sa.ForeignKeyConstraint(
            ["replaced_by_assignment_id", "tenant_id"],
            ["card_assignments.id", "card_assignments.tenant_id"],
            name="fk_card_assignments_replaced_by_tenant",
        ),
        sa.UniqueConstraint("id", "tenant_id", name="uq_card_assignments_id_tenant"),
        sa.CheckConstraint(
            "status IN ('pending', 'active', 'lost', 'blocked', 'expired', 'replaced', 'revoked')",
            name="ck_card_assignments_status",
        ),
    )
    op.create_index(
        "ix_card_assignments_tenant_student",
        "card_assignments",
        ["tenant_id", "student_id", "status"],
    )
    op.create_index(
        "ix_card_assignments_tenant_card",
        "card_assignments",
        ["tenant_id", "physical_card_id", "status"],
    )
    op.execute(
        f"""
        CREATE UNIQUE INDEX uq_card_assignments_one_active_student
        ON card_assignments (tenant_id, student_id)
        WHERE {ACTIVE_ASSIGNMENT_PREDICATE}
        """
    )
    op.execute(
        f"""
        CREATE UNIQUE INDEX uq_card_assignments_one_active_card
        ON card_assignments (tenant_id, physical_card_id)
        WHERE {ACTIVE_ASSIGNMENT_PREDICATE}
        """
    )

    for table in TENANT_TABLES:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        op.execute(
            f"""
            CREATE POLICY tenant_isolation ON {table}
              USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
              WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
            """
        )

    op.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON physical_cards, card_assignments TO schoolpass_app")
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
    for table in reversed(TENANT_TABLES):
        op.execute(f"DROP POLICY IF EXISTS tenant_isolation ON {table}")
        op.drop_table(table)
