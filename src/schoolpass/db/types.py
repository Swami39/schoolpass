"""Shared SQLAlchemy column types for UUID, timestamptz, and currency."""

from __future__ import annotations

from sqlalchemy import DateTime, Numeric, String, Uuid

uuid_pk = Uuid(as_uuid=True)
timestamptz = DateTime(timezone=True)
money = Numeric(12, 2)
currency_code = String(3)
