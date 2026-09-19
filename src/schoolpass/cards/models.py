from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import CheckConstraint, DateTime, ForeignKeyConstraint, String, Text, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from schoolpass.db.mixins import TimestampMixin, UUIDPrimaryKeyMixin
from schoolpass.db.session import Base


class PhysicalCard(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "physical_cards"

    tenant_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    hf_uid: Mapped[str | None] = mapped_column(String(128), nullable=True)
    uhf_epc: Mapped[str | None] = mapped_column(String(128), nullable=True)
    uhf_tid: Mapped[str | None] = mapped_column(String(128), nullable=True)
    profile: Mapped[str] = mapped_column(String(32), default="uid_only", nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="inventory", nullable=False)
    manufactured_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        UniqueConstraint("id", "tenant_id", name="uq_physical_cards_id_tenant"),
        CheckConstraint(
            "profile IN ('uid_only', 'ntag_sig', 'desfire')",
            name="ck_physical_cards_profile",
        ),
        CheckConstraint(
            "status IN ('inventory', 'active', 'blocked', 'retired')",
            name="ck_physical_cards_status",
        ),
    )


class CardAssignment(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "card_assignments"

    tenant_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    student_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    physical_card_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="pending", nullable=False)
    issued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    activated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoke_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    replaced_by_assignment_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True)

    __table_args__ = (
        ForeignKeyConstraint(
            ["student_id", "tenant_id"],
            ["students.id", "students.tenant_id"],
            name="fk_card_assignments_student_tenant",
        ),
        ForeignKeyConstraint(
            ["physical_card_id", "tenant_id"],
            ["physical_cards.id", "physical_cards.tenant_id"],
            name="fk_card_assignments_card_tenant",
        ),
        ForeignKeyConstraint(
            ["replaced_by_assignment_id", "tenant_id"],
            ["card_assignments.id", "card_assignments.tenant_id"],
            name="fk_card_assignments_replaced_by_tenant",
        ),
        UniqueConstraint("id", "tenant_id", name="uq_card_assignments_id_tenant"),
        CheckConstraint(
            "status IN ('pending', 'active', 'lost', 'blocked', 'expired', 'replaced', 'revoked')",
            name="ck_card_assignments_status",
        ),
    )
