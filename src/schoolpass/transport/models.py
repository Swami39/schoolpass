from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKeyConstraint,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column

from schoolpass.db.mixins import TimestampMixin, UUIDPrimaryKeyMixin
from schoolpass.db.session import Base


class Bus(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "buses"

    tenant_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    registration_number: Mapped[str] = mapped_column(String(32), nullable=False)
    fleet_number: Mapped[str | None] = mapped_column(String(32), nullable=True)
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    capacity: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="active", nullable=False)

    __table_args__ = (
        UniqueConstraint("id", "tenant_id", name="uq_buses_id_tenant"),
        UniqueConstraint("tenant_id", "registration_number", name="uq_buses_tenant_registration"),
        CheckConstraint("capacity > 0", name="ck_buses_capacity"),
        CheckConstraint(
            "status IN ('active', 'inactive', 'maintenance', 'retired')",
            name="ck_buses_status",
        ),
    )


class TransportAttendant(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "transport_attendants"

    tenant_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    user_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    employee_code: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="active", nullable=False)

    __table_args__ = (
        ForeignKeyConstraint(
            ["tenant_id", "user_id"],
            ["staff_profiles.tenant_id", "staff_profiles.user_id"],
            name="fk_transport_attendants_staff_tenant",
        ),
        UniqueConstraint("id", "tenant_id", name="uq_transport_attendants_id_tenant"),
        UniqueConstraint("tenant_id", "user_id", name="uq_transport_attendants_tenant_user"),
        UniqueConstraint("tenant_id", "employee_code", name="uq_transport_attendants_tenant_code"),
        CheckConstraint("status IN ('active', 'inactive')", name="ck_transport_attendants_status"),
    )


class Route(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "routes"

    tenant_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    code: Mapped[str] = mapped_column(String(64), nullable=False)
    direction: Mapped[str] = mapped_column(String(16), nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="active", nullable=False)

    __table_args__ = (
        UniqueConstraint("id", "tenant_id", name="uq_routes_id_tenant"),
        UniqueConstraint("tenant_id", "code", name="uq_routes_tenant_code"),
        CheckConstraint("direction IN ('pickup', 'dropoff')", name="ck_routes_direction"),
        CheckConstraint("status IN ('active', 'inactive', 'retired')", name="ck_routes_status"),
    )


class RouteStop(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "route_stops"

    tenant_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    route_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    latitude: Mapped[Decimal] = mapped_column(Numeric(9, 6), nullable=False)
    longitude: Mapped[Decimal] = mapped_column(Numeric(9, 6), nullable=False)
    geofence_radius_meters: Mapped[int] = mapped_column(Integer, default=100, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="active", nullable=False)

    __table_args__ = (
        ForeignKeyConstraint(
            ["route_id", "tenant_id"],
            ["routes.id", "routes.tenant_id"],
            name="fk_route_stops_route_tenant",
        ),
        UniqueConstraint("id", "tenant_id", name="uq_route_stops_id_tenant"),
        UniqueConstraint("id", "route_id", "tenant_id", name="uq_route_stops_id_route_tenant"),
        UniqueConstraint("tenant_id", "route_id", "sequence", name="uq_route_stops_route_sequence"),
        CheckConstraint("sequence > 0", name="ck_route_stops_sequence"),
        CheckConstraint("latitude >= -90 AND latitude <= 90", name="ck_route_stops_latitude"),
        CheckConstraint("longitude >= -180 AND longitude <= 180", name="ck_route_stops_longitude"),
        CheckConstraint("geofence_radius_meters > 0", name="ck_route_stops_geofence"),
        CheckConstraint("status IN ('active', 'inactive', 'retired')", name="ck_route_stops_status"),
    )


class TransportAssignment(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "transport_assignments"

    tenant_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    student_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    route_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    stop_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    effective_from: Mapped[date] = mapped_column(Date, nullable=False)
    effective_to: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="active", nullable=False)

    __table_args__ = (
        ForeignKeyConstraint(
            ["student_id", "tenant_id"],
            ["students.id", "students.tenant_id"],
            name="fk_transport_assignments_student_tenant",
        ),
        ForeignKeyConstraint(
            ["route_id", "tenant_id"],
            ["routes.id", "routes.tenant_id"],
            name="fk_transport_assignments_route_tenant",
        ),
        ForeignKeyConstraint(
            ["stop_id", "route_id", "tenant_id"],
            ["route_stops.id", "route_stops.route_id", "route_stops.tenant_id"],
            name="fk_transport_assignments_stop_route_tenant",
        ),
        UniqueConstraint("id", "tenant_id", name="uq_transport_assignments_id_tenant"),
        CheckConstraint(
            "status IN ('active', 'suspended', 'cancelled', 'expired')",
            name="ck_transport_assignments_status",
        ),
        CheckConstraint(
            "effective_to IS NULL OR effective_to >= effective_from",
            name="ck_transport_assignments_dates",
        ),
    )


class Trip(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "trips"

    tenant_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    bus_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    route_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    attendant_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    service_date: Mapped[date] = mapped_column(Date, nullable=False)
    shift: Mapped[str] = mapped_column(String(16), nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="scheduled", nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        ForeignKeyConstraint(
            ["bus_id", "tenant_id"],
            ["buses.id", "buses.tenant_id"],
            name="fk_trips_bus_tenant",
        ),
        ForeignKeyConstraint(
            ["route_id", "tenant_id"],
            ["routes.id", "routes.tenant_id"],
            name="fk_trips_route_tenant",
        ),
        ForeignKeyConstraint(
            ["attendant_id", "tenant_id"],
            ["transport_attendants.id", "transport_attendants.tenant_id"],
            name="fk_trips_attendant_tenant",
        ),
        UniqueConstraint("id", "tenant_id", name="uq_trips_id_tenant"),
        CheckConstraint("shift IN ('pickup', 'dropoff')", name="ck_trips_shift"),
        CheckConstraint(
            "status IN ('scheduled', 'boarding', 'in_progress', 'completed', 'cancelled')",
            name="ck_trips_status",
        ),
    )


class TripStop(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "trip_stops"

    tenant_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    trip_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    route_stop_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True)
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    latitude: Mapped[Decimal] = mapped_column(Numeric(9, 6), nullable=False)
    longitude: Mapped[Decimal] = mapped_column(Numeric(9, 6), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        ForeignKeyConstraint(
            ["trip_id", "tenant_id"],
            ["trips.id", "trips.tenant_id"],
            name="fk_trip_stops_trip_tenant",
        ),
        ForeignKeyConstraint(
            ["route_stop_id", "tenant_id"],
            ["route_stops.id", "route_stops.tenant_id"],
            name="fk_trip_stops_route_stop_tenant",
        ),
        UniqueConstraint("id", "tenant_id", name="uq_trip_stops_id_tenant"),
        UniqueConstraint("tenant_id", "trip_id", "sequence", name="uq_trip_stops_trip_sequence"),
        CheckConstraint("sequence > 0", name="ck_trip_stops_sequence"),
        CheckConstraint("latitude >= -90 AND latitude <= 90", name="ck_trip_stops_latitude"),
        CheckConstraint("longitude >= -180 AND longitude <= 180", name="ck_trip_stops_longitude"),
    )
