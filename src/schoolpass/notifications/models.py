from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, ForeignKeyConstraint, String, Text, UniqueConstraint, Uuid
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from schoolpass.db.mixins import TimestampMixin, UUIDPrimaryKeyMixin, utcnow
from schoolpass.db.session import Base


class Notification(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "notifications"

    tenant_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    recipient_user_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("users.id"), nullable=False)
    notification_type: Mapped[str] = mapped_column(String(64), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    correlation_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    idempotency_key: Mapped[str] = mapped_column(String(256), nullable=False)
    schema_version: Mapped[int] = mapped_column(default=1, nullable=False)
    delivery_status: Mapped[str] = mapped_column(String(32), default="pending", nullable=False)
    reference_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    reference_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True)

    __table_args__ = (
        UniqueConstraint("tenant_id", "idempotency_key", name="uq_notifications_tenant_idempotency"),
        UniqueConstraint("id", "tenant_id", name="uq_notifications_id_tenant"),
        CheckConstraint(
            "delivery_status IN ('pending', 'queued', 'sent', 'failed', "
            "'skipped_preference', 'skipped_no_device')",
            name="ck_notifications_delivery_status",
        ),
    )


class NotificationDevice(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "notification_devices"

    tenant_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    user_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("users.id"), nullable=False)
    platform: Mapped[str] = mapped_column(String(32), nullable=False)
    fcm_token: Mapped[str] = mapped_column(String(512), nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="active", nullable=False)
    last_success_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_failure_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_failure_code: Mapped[str | None] = mapped_column(String(64), nullable=True)

    __table_args__ = (
        UniqueConstraint("tenant_id", "fcm_token", name="uq_notification_devices_tenant_token"),
        UniqueConstraint("id", "tenant_id", name="uq_notification_devices_id_tenant"),
        CheckConstraint("status IN ('active', 'revoked')", name="ck_notification_devices_status"),
    )


class NotificationDelivery(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "notification_deliveries"

    tenant_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    notification_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    device_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    provider: Mapped[str] = mapped_column(String(32), nullable=False)
    attempt: Mapped[int] = mapped_column(default=1, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    provider_message_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    failure_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    __table_args__ = (
        ForeignKeyConstraint(
            ["notification_id", "tenant_id"],
            ["notifications.id", "notifications.tenant_id"],
            name="fk_notification_deliveries_notification_tenant",
        ),
        ForeignKeyConstraint(
            ["device_id", "tenant_id"],
            ["notification_devices.id", "notification_devices.tenant_id"],
            name="fk_notification_deliveries_device_tenant",
        ),
        UniqueConstraint(
            "tenant_id",
            "notification_id",
            "device_id",
            "attempt",
            name="uq_notification_deliveries_attempt",
        ),
        UniqueConstraint("id", "tenant_id", name="uq_notification_deliveries_id_tenant"),
        CheckConstraint(
            "status IN ('sent', 'failed', 'skipped')",
            name="ck_notification_deliveries_status",
        ),
    )


class NotificationPreference(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "notification_preferences"

    tenant_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    user_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("users.id"), nullable=False)
    notification_type: Mapped[str] = mapped_column(String(64), nullable=False)
    push_enabled: Mapped[bool] = mapped_column(default=True, nullable=False)

    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "user_id",
            "notification_type",
            name="uq_notification_preferences_user_type",
        ),
        UniqueConstraint("id", "tenant_id", name="uq_notification_preferences_id_tenant"),
    )
