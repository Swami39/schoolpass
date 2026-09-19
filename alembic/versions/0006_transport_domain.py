"""Transport foundation — buses, routes, assignments, trips.

Revision ID: 0006_transport_domain
Revises: 0005_attendance
Create Date: 2026-09-19
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0006_transport_domain"
down_revision = "0005_attendance"
branch_labels = None
depends_on = None

NEW_PERMISSIONS = {
    "buses:read": "Read buses",
    "buses:create": "Create buses",
    "buses:update": "Update buses",
    "routes:read": "Read transport routes",
    "routes:create": "Create transport routes",
    "routes:update": "Update transport routes",
    "route_stops:read": "Read route stops",
    "route_stops:write": "Manage route stops",
    "transport_assignments:read": "Read student transport assignments",
    "transport_assignments:write": "Manage student transport assignments",
    "transport_attendants:read": "Read transport attendants",
    "transport_attendants:write": "Manage transport attendants",
    "trips:read": "Read transport trips",
    "trips:write": "Manage transport trips",
}

ROLE_PERMISSIONS_DELTA = {
    "platform_super_admin": tuple(NEW_PERMISSIONS),
    "platform_support": (
        "buses:read",
        "routes:read",
        "route_stops:read",
        "transport_assignments:read",
        "transport_attendants:read",
        "trips:read",
    ),
    "school_admin": tuple(NEW_PERMISSIONS),
    "school_finance": ("buses:read", "routes:read", "transport_assignments:read", "trips:read"),
    "teacher": ("routes:read", "route_stops:read", "transport_assignments:read", "trips:read"),
    "bus_attendant": (
        "buses:read",
        "routes:read",
        "route_stops:read",
        "transport_assignments:read",
        "trips:read",
        "trips:write",
    ),
    "parent": ("routes:read", "route_stops:read", "transport_assignments:read", "trips:read"),
}

RLS_TABLES = (
    "buses",
    "transport_attendants",
    "routes",
    "route_stops",
    "transport_assignments",
    "trips",
    "trip_stops",
)


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS btree_gist")

    op.create_table(
        "buses",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("registration_number", sa.String(32), nullable=False),
        sa.Column("fleet_number", sa.String(32), nullable=True),
        sa.Column("display_name", sa.String(255), nullable=False),
        sa.Column("capacity", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("id", "tenant_id", name="uq_buses_id_tenant"),
        sa.UniqueConstraint("tenant_id", "registration_number", name="uq_buses_tenant_registration"),
        sa.CheckConstraint("capacity > 0", name="ck_buses_capacity"),
        sa.CheckConstraint(
            "status IN ('active', 'inactive', 'maintenance', 'retired')",
            name="ck_buses_status",
        ),
    )
    op.create_index("ix_buses_tenant_status", "buses", ["tenant_id", "status"])
    op.execute(
        """
        CREATE UNIQUE INDEX uq_buses_tenant_fleet_number
        ON buses (tenant_id, fleet_number)
        WHERE fleet_number IS NOT NULL
        """
    )

    op.create_table(
        "transport_attendants",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("employee_code", sa.String(64), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(
            ["tenant_id", "user_id"],
            ["staff_profiles.tenant_id", "staff_profiles.user_id"],
            name="fk_transport_attendants_staff_tenant",
        ),
        sa.UniqueConstraint("id", "tenant_id", name="uq_transport_attendants_id_tenant"),
        sa.UniqueConstraint("tenant_id", "user_id", name="uq_transport_attendants_tenant_user"),
        sa.UniqueConstraint("tenant_id", "employee_code", name="uq_transport_attendants_tenant_code"),
        sa.CheckConstraint("status IN ('active', 'inactive')", name="ck_transport_attendants_status"),
    )

    op.create_table(
        "routes",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("code", sa.String(64), nullable=False),
        sa.Column("direction", sa.String(16), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("id", "tenant_id", name="uq_routes_id_tenant"),
        sa.UniqueConstraint("tenant_id", "code", name="uq_routes_tenant_code"),
        sa.CheckConstraint("direction IN ('pickup', 'dropoff')", name="ck_routes_direction"),
        sa.CheckConstraint("status IN ('active', 'inactive', 'retired')", name="ck_routes_status"),
    )
    op.create_index("ix_routes_tenant_status", "routes", ["tenant_id", "status"])

    op.create_table(
        "route_stops",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("route_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("latitude", sa.Numeric(9, 6), nullable=False),
        sa.Column("longitude", sa.Numeric(9, 6), nullable=False),
        sa.Column("geofence_radius_meters", sa.Integer(), nullable=False, server_default="100"),
        sa.Column("status", sa.String(32), nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(
            ["route_id", "tenant_id"],
            ["routes.id", "routes.tenant_id"],
            name="fk_route_stops_route_tenant",
        ),
        sa.UniqueConstraint("id", "tenant_id", name="uq_route_stops_id_tenant"),
        sa.UniqueConstraint("id", "route_id", "tenant_id", name="uq_route_stops_id_route_tenant"),
        sa.UniqueConstraint("tenant_id", "route_id", "sequence", name="uq_route_stops_route_sequence"),
        sa.CheckConstraint("sequence > 0", name="ck_route_stops_sequence"),
        sa.CheckConstraint("latitude >= -90 AND latitude <= 90", name="ck_route_stops_latitude"),
        sa.CheckConstraint("longitude >= -180 AND longitude <= 180", name="ck_route_stops_longitude"),
        sa.CheckConstraint("geofence_radius_meters > 0", name="ck_route_stops_geofence"),
        sa.CheckConstraint("status IN ('active', 'inactive', 'retired')", name="ck_route_stops_status"),
    )
    op.create_index("ix_route_stops_route_sequence", "route_stops", ["tenant_id", "route_id", "sequence"])

    op.create_table(
        "transport_assignments",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("student_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("route_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("stop_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("effective_from", sa.Date(), nullable=False),
        sa.Column("effective_to", sa.Date(), nullable=True),
        sa.Column("status", sa.String(32), nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(
            ["student_id", "tenant_id"],
            ["students.id", "students.tenant_id"],
            name="fk_transport_assignments_student_tenant",
        ),
        sa.ForeignKeyConstraint(
            ["route_id", "tenant_id"],
            ["routes.id", "routes.tenant_id"],
            name="fk_transport_assignments_route_tenant",
        ),
        sa.ForeignKeyConstraint(
            ["stop_id", "route_id", "tenant_id"],
            ["route_stops.id", "route_stops.route_id", "route_stops.tenant_id"],
            name="fk_transport_assignments_stop_route_tenant",
        ),
        sa.UniqueConstraint("id", "tenant_id", name="uq_transport_assignments_id_tenant"),
        sa.CheckConstraint(
            "status IN ('active', 'suspended', 'cancelled', 'expired')",
            name="ck_transport_assignments_status",
        ),
        sa.CheckConstraint(
            "effective_to IS NULL OR effective_to >= effective_from",
            name="ck_transport_assignments_dates",
        ),
    )
    op.create_index(
        "ix_transport_assignments_student_status",
        "transport_assignments",
        ["tenant_id", "student_id", "status"],
    )
    op.create_index(
        "ix_transport_assignments_route_status",
        "transport_assignments",
        ["tenant_id", "route_id", "status"],
    )
    op.execute(
        """
        CREATE UNIQUE INDEX uq_transport_assignments_one_active_student
        ON transport_assignments (tenant_id, student_id)
        WHERE status = 'active'
        """
    )
    op.execute(
        """
        ALTER TABLE transport_assignments
        ADD CONSTRAINT ex_transport_assignments_no_overlap_active
        EXCLUDE USING gist (
            tenant_id WITH =,
            student_id WITH =,
            daterange(effective_from, effective_to, '[]') WITH &&
        )
        WHERE (status = 'active')
        """
    )

    op.create_table(
        "trips",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("bus_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("route_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("attendant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("service_date", sa.Date(), nullable=False),
        sa.Column("shift", sa.String(16), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="scheduled"),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(
            ["bus_id", "tenant_id"],
            ["buses.id", "buses.tenant_id"],
            name="fk_trips_bus_tenant",
        ),
        sa.ForeignKeyConstraint(
            ["route_id", "tenant_id"],
            ["routes.id", "routes.tenant_id"],
            name="fk_trips_route_tenant",
        ),
        sa.ForeignKeyConstraint(
            ["attendant_id", "tenant_id"],
            ["transport_attendants.id", "transport_attendants.tenant_id"],
            name="fk_trips_attendant_tenant",
        ),
        sa.UniqueConstraint("id", "tenant_id", name="uq_trips_id_tenant"),
        sa.CheckConstraint("shift IN ('pickup', 'dropoff')", name="ck_trips_shift"),
        sa.CheckConstraint(
            "status IN ('scheduled', 'boarding', 'in_progress', 'completed', 'cancelled')",
            name="ck_trips_status",
        ),
    )
    op.create_index("ix_trips_tenant_service_date", "trips", ["tenant_id", "service_date"])
    op.create_index("ix_trips_bus_service_date", "trips", ["tenant_id", "bus_id", "service_date"])
    op.create_index("ix_trips_attendant_service_date", "trips", ["tenant_id", "attendant_id", "service_date"])
    op.create_index("ix_trips_tenant_status", "trips", ["tenant_id", "status"])

    op.create_table(
        "trip_stops",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("trip_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("route_stop_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("latitude", sa.Numeric(9, 6), nullable=False),
        sa.Column("longitude", sa.Numeric(9, 6), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(
            ["trip_id", "tenant_id"],
            ["trips.id", "trips.tenant_id"],
            name="fk_trip_stops_trip_tenant",
        ),
        sa.ForeignKeyConstraint(
            ["route_stop_id", "tenant_id"],
            ["route_stops.id", "route_stops.tenant_id"],
            name="fk_trip_stops_route_stop_tenant",
        ),
        sa.UniqueConstraint("id", "tenant_id", name="uq_trip_stops_id_tenant"),
        sa.UniqueConstraint("tenant_id", "trip_id", "sequence", name="uq_trip_stops_trip_sequence"),
        sa.CheckConstraint("sequence > 0", name="ck_trip_stops_sequence"),
        sa.CheckConstraint("latitude >= -90 AND latitude <= 90", name="ck_trip_stops_latitude"),
        sa.CheckConstraint("longitude >= -180 AND longitude <= 180", name="ck_trip_stops_longitude"),
    )
    op.create_index("ix_trip_stops_trip_sequence", "trip_stops", ["tenant_id", "trip_id", "sequence"])

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
          buses,
          transport_attendants,
          routes,
          route_stops,
          transport_assignments,
          trips,
          trip_stops
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
    op.drop_table("trip_stops")
    op.drop_table("trips")
    op.execute("ALTER TABLE transport_assignments DROP CONSTRAINT IF EXISTS ex_transport_assignments_no_overlap_active")
    op.drop_table("transport_assignments")
    op.drop_table("route_stops")
    op.drop_table("routes")
    op.drop_table("transport_attendants")
    op.drop_table("buses")
