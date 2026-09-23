"""Push device app label + push_register permissions for all app roles.

Revision ID: 0017_push_device_app_label
Revises: 0016_tenant_school_profile
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0017_push_device_app_label"
down_revision = "0016_tenant_school_profile"
branch_labels = None
depends_on = None

NEW_PERMISSIONS = {
    "teacher:push_register": "Register mobile device for push notifications",
    "bus_attendant:push_register": "Register mobile device for push notifications",
    "school_admin:push_register": "Register mobile device for push notifications",
}

ROLE_PERMISSIONS_DELTA = {
    "platform_super_admin": (
        "teacher:push_register",
        "bus_attendant:push_register",
        "school_admin:push_register",
    ),
    "teacher": ("teacher:push_register",),
    "bus_attendant": ("bus_attendant:push_register",),
    "school_admin": ("school_admin:push_register",),
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
    op.add_column("notification_devices", sa.Column("app_label", sa.String(32), nullable=True))
    op.add_column("notification_devices", sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True))
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
    op.drop_column("notification_devices", "last_seen_at")
    op.drop_column("notification_devices", "app_label")
