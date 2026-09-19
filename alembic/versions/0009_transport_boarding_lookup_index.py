"""Index for NFC dropoff sequence lookups on transport boarding records.

Revision ID: 0009_transport_boarding_lookup_index
Revises: 0008_transport_nfc_attendance
Create Date: 2026-09-19
"""

from __future__ import annotations

from alembic import op

revision = "0009_nfc_boarding_index"
down_revision = "0008_transport_nfc_attendance"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index(
        "ix_transport_boarding_trip_student_occurred",
        "transport_boarding_records",
        ["tenant_id", "trip_id", "student_id", "event_type", "occurred_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_transport_boarding_trip_student_occurred", table_name="transport_boarding_records")
