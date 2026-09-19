"""Tenant school profile fields and tenant:write permission (Phase 10.1).

Revision ID: 0016_tenant_school_profile
Revises: 0015_teacher_domain
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0016_tenant_school_profile"
down_revision = "0015_teacher_domain"
branch_labels = None
depends_on = None

NEW_PERMISSIONS = {
    "tenant:write": "Update tenant/school profile",
}

ROLE_PERMISSIONS_DELTA = {
    "platform_super_admin": ("tenant:write",),
    "school_admin": ("tenant:write",),
}


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


def upgrade() -> None:
    op.add_column("tenants", sa.Column("display_name", sa.String(255), nullable=True))
    op.add_column("tenants", sa.Column("contact_email", sa.String(255), nullable=True))
    op.add_column("tenants", sa.Column("contact_phone", sa.String(32), nullable=True))
    op.add_column("tenants", sa.Column("address_line1", sa.String(255), nullable=True))
    op.add_column("tenants", sa.Column("city", sa.String(128), nullable=True))
    op.add_column("tenants", sa.Column("state", sa.String(128), nullable=True))
    op.add_column("tenants", sa.Column("postal_code", sa.String(32), nullable=True))
    op.add_column("tenants", sa.Column("logo_file_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.create_foreign_key(
        "fk_tenants_logo_file_tenant",
        "tenants",
        "files",
        ["logo_file_id", "id"],
        ["id", "tenant_id"],
    )
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
    op.drop_constraint("fk_tenants_logo_file_tenant", "tenants", type_="foreignkey")
    op.drop_column("tenants", "logo_file_id")
    op.drop_column("tenants", "postal_code")
    op.drop_column("tenants", "state")
    op.drop_column("tenants", "city")
    op.drop_column("tenants", "address_line1")
    op.drop_column("tenants", "contact_phone")
    op.drop_column("tenants", "contact_email")
    op.drop_column("tenants", "display_name")
