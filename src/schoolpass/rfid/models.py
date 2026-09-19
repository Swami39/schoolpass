from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKeyConstraint,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column

from schoolpass.db.mixins import TimestampMixin, UUIDPrimaryKeyMixin
from schoolpass.db.session import Base


class RfidReader(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "rfid_readers"

    tenant_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    location: Mapped[str | None] = mapped_column(String(255), nullable=True)
    gate_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True)
    direction_mode: Mapped[str | None] = mapped_column(String(32), nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="active", nullable=False)

    __table_args__ = (
        UniqueConstraint("id", "tenant_id", name="uq_rfid_readers_id_tenant"),
        CheckConstraint("status IN ('active', 'blocked', 'retired')", name="ck_rfid_readers_status"),
    )


class RfidDevice(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Global device directory — no RLS."""

    __tablename__ = "rfid_devices"

    device_id: Mapped[str] = mapped_column(String(128), nullable=False, unique=True)
    tenant_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    reader_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    key_version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="active", nullable=False)
    device_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        ForeignKeyConstraint(
            ["reader_id", "tenant_id"],
            ["rfid_readers.id", "rfid_readers.tenant_id"],
            name="fk_rfid_devices_reader_tenant",
        ),
        CheckConstraint("status IN ('active', 'blocked', 'retired')", name="ck_rfid_devices_status"),
    )


class RfidDeviceKey(UUIDPrimaryKeyMixin, Base):
    """Encrypted HMAC secrets — no RLS."""

    __tablename__ = "rfid_device_keys"

    device_uuid: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    key_version: Mapped[int] = mapped_column(Integer, nullable=False)
    secret_encrypted: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="active", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        UniqueConstraint("device_uuid", "key_version", name="uq_rfid_device_keys_device_version"),
        CheckConstraint("status IN ('active', 'revoked')", name="ck_rfid_device_keys_status"),
    )


class RfidEvent(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "rfid_events"

    tenant_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    reader_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    device_uuid: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    device_event_id: Mapped[str] = mapped_column(String(128), nullable=False)
    physical_card_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True)
    assignment_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True)
    student_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True)
    hf_uid: Mapped[str | None] = mapped_column(String(128), nullable=True)
    uhf_epc: Mapped[str | None] = mapped_column(String(128), nullable=True)
    uhf_tid: Mapped[str | None] = mapped_column(String(128), nullable=True)
    antenna: Mapped[int | None] = mapped_column(Integer, nullable=True)
    rssi: Mapped[Decimal | None] = mapped_column(Numeric(8, 2), nullable=True)
    direction: Mapped[str | None] = mapped_column(String(32), nullable=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    signature_key_version: Mapped[int] = mapped_column(Integer, nullable=False)
    ingest_status: Mapped[str] = mapped_column(String(32), default="accepted", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        ForeignKeyConstraint(
            ["reader_id", "tenant_id"],
            ["rfid_readers.id", "rfid_readers.tenant_id"],
            name="fk_rfid_events_reader_tenant",
        ),
        ForeignKeyConstraint(["device_uuid"], ["rfid_devices.id"], name="fk_rfid_events_device"),
        ForeignKeyConstraint(
            ["physical_card_id", "tenant_id"],
            ["physical_cards.id", "physical_cards.tenant_id"],
            name="fk_rfid_events_card_tenant",
        ),
        ForeignKeyConstraint(
            ["assignment_id", "tenant_id"],
            ["card_assignments.id", "card_assignments.tenant_id"],
            name="fk_rfid_events_assignment_tenant",
        ),
        ForeignKeyConstraint(
            ["student_id", "tenant_id"],
            ["students.id", "students.tenant_id"],
            name="fk_rfid_events_student_tenant",
        ),
        UniqueConstraint("id", "tenant_id", name="uq_rfid_events_id_tenant"),
        UniqueConstraint("tenant_id", "reader_id", "device_event_id", name="uq_rfid_events_idempotency"),
    )


class RfidEventProcessing(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "rfid_event_processing"

    tenant_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    rfid_event_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="pending", nullable=False)
    attempt_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    last_error_message: Mapped[str | None] = mapped_column(String(255), nullable=True)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        ForeignKeyConstraint(
            ["rfid_event_id", "tenant_id"],
            ["rfid_events.id", "rfid_events.tenant_id"],
            name="fk_rfid_processing_event_tenant",
        ),
        UniqueConstraint("rfid_event_id", name="uq_rfid_event_processing_event"),
        UniqueConstraint("id", "tenant_id", name="uq_rfid_event_processing_id_tenant"),
        CheckConstraint(
            "status IN ('pending', 'processing', 'processed', 'rejected', 'failed')",
            name="ck_rfid_event_processing_status",
        ),
    )


class RfidObservation(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "rfid_observations"

    tenant_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    rfid_event_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    physical_card_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True)
    assignment_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True)
    student_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True)
    resolution_status: Mapped[str] = mapped_column(String(32), nullable=False)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        ForeignKeyConstraint(
            ["rfid_event_id", "tenant_id"],
            ["rfid_events.id", "rfid_events.tenant_id"],
            name="fk_rfid_observations_event_tenant",
        ),
        UniqueConstraint("rfid_event_id", name="uq_rfid_observations_event"),
        UniqueConstraint("id", "tenant_id", name="uq_rfid_observations_id_tenant"),
    )


class RfidIngestReject(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "rfid_ingest_rejects"

    tenant_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True)
    device_external_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    reader_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True)
    reason_code: Mapped[str] = mapped_column(String(64), nullable=False)
    correlation_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
