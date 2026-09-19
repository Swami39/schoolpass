from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class CardCreate(BaseModel):
    hf_uid: str | None = Field(default=None, max_length=128)
    uhf_epc: str | None = Field(default=None, max_length=128)
    uhf_tid: str | None = Field(default=None, max_length=128)
    profile: str = Field(default="uid_only", max_length=32)
    manufactured_at: datetime | None = None


class CardUpdate(BaseModel):
    manufactured_at: datetime | None = None


class CardStatusChange(BaseModel):
    status: str = Field(max_length=32)


class CardResponse(BaseModel):
    id: UUID
    tenant_id: UUID
    hf_uid: str | None
    uhf_epc: str | None
    uhf_tid: str | None
    profile: str
    status: str
    manufactured_at: datetime | None
    created_at: datetime
    updated_at: datetime


class CardListResponse(BaseModel):
    items: list[CardResponse]
    next_cursor: str | None = None


class AssignmentCreate(BaseModel):
    student_id: UUID
    physical_card_id: UUID


class AssignmentResponse(BaseModel):
    id: UUID
    tenant_id: UUID
    student_id: UUID
    physical_card_id: UUID
    status: str
    issued_at: datetime
    activated_at: datetime | None
    revoked_at: datetime | None
    revoke_reason: str | None
    replaced_by_assignment_id: UUID | None
    created_at: datetime
    updated_at: datetime


class AssignmentListResponse(BaseModel):
    items: list[AssignmentResponse]
    next_cursor: str | None = None


class RevokeRequest(BaseModel):
    reason: str = Field(min_length=1, max_length=255)


class ReplaceRequest(BaseModel):
    physical_card_id: UUID | None = None
    new_card: CardCreate | None = None
    activate: bool = True
    revoke_reason: str = Field(default="replaced", max_length=255)
