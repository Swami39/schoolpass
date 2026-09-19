"""Transport trip concurrency hardening — active trip uniqueness.

Revision ID: 0007_transport_trip_hardening
Revises: 0006_transport_domain
Create Date: 2026-09-19
"""

from __future__ import annotations

from alembic import op

revision = "0007_transport_trip_hardening"
down_revision = "0006_transport_domain"
branch_labels = None
depends_on = None

ACTIVE_TRIP_STATUSES = ("scheduled", "boarding", "in_progress")


def upgrade() -> None:
    status_list = ", ".join(f"'{s}'" for s in ACTIVE_TRIP_STATUSES)
    op.execute(
        f"""
        CREATE UNIQUE INDEX uq_trips_one_active_bus_service_date
        ON trips (tenant_id, bus_id, service_date)
        WHERE status IN ({status_list})
        """
    )
    op.execute(
        f"""
        CREATE UNIQUE INDEX uq_trips_one_active_attendant_service_date
        ON trips (tenant_id, attendant_id, service_date)
        WHERE status IN ({status_list})
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS uq_trips_one_active_attendant_service_date")
    op.execute("DROP INDEX IF EXISTS uq_trips_one_active_bus_service_date")
