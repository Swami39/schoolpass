from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from schoolpass.cards import schemas as card_schemas
from schoolpass.transport import schemas as transport_schemas


class AdminCardCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    hf_uid: str | None = Field(default=None, max_length=128)
    uhf_epc: str | None = Field(default=None, max_length=128)
    uhf_tid: str | None = Field(default=None, max_length=128)
    profile: str = Field(default="uid_only", max_length=32)
    manufactured_at: datetime | None = None


class AdminAssignmentCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    student_id: UUID
    physical_card_id: UUID


class AdminReplaceAssignment(BaseModel):
    model_config = ConfigDict(extra="forbid")

    physical_card_id: UUID
    revoke_reason: str = Field(default="replaced", max_length=255)
    activate: bool = True


class AdminRevokeAssignment(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: str = Field(min_length=1, max_length=255)


class AdminReaderCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=255)
    location: str | None = Field(default=None, max_length=255)
    gate_id: UUID | None = None
    direction_mode: str | None = Field(default=None, max_length=32)


class AdminReaderUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=1, max_length=255)
    location: str | None = Field(default=None, max_length=255)
    gate_id: UUID | None = None
    direction_mode: str | None = Field(default=None, max_length=32)
    status: str | None = None


class AdminBusCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    registration_number: str = Field(min_length=1, max_length=64)
    fleet_number: str | None = Field(default=None, max_length=64)
    display_name: str = Field(min_length=1, max_length=128)
    capacity: int = Field(ge=1, le=500)


class AdminBusUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    fleet_number: str | None = Field(default=None, max_length=64)
    display_name: str | None = Field(default=None, max_length=128)
    capacity: int | None = Field(default=None, ge=1, le=500)


CardResponse = card_schemas.CardResponse
CardListResponse = card_schemas.CardListResponse
AssignmentResponse = card_schemas.AssignmentResponse
AssignmentListResponse = card_schemas.AssignmentListResponse
BusResponse = transport_schemas.BusResponse
BusListResponse = transport_schemas.BusListResponse
TripResponse = transport_schemas.TripResponse
TripListResponse = transport_schemas.TripListResponse
TransportAssignmentResponse = transport_schemas.TransportAssignmentResponse
TransportAssignmentListResponse = transport_schemas.TransportAssignmentListResponse
