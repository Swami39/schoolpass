from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy.orm import Mapped, mapped_column

from schoolpass.db.types import timestamptz, uuid_pk


def utcnow() -> datetime:
    return datetime.now(UTC)


class UUIDPrimaryKeyMixin:
    id: Mapped[UUID] = mapped_column(uuid_pk, primary_key=True, default=uuid4)


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(timestamptz, default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(timestamptz, default=utcnow, onupdate=utcnow, nullable=False)
