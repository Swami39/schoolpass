from __future__ import annotations

from datetime import date, datetime
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
TransportAttendantResponse = transport_schemas.TransportAttendantResponse
TransportAttendantListResponse = transport_schemas.TransportAttendantListResponse
RouteResponse = transport_schemas.RouteResponse
RouteListResponse = transport_schemas.RouteListResponse
RouteStopResponse = transport_schemas.RouteStopResponse
RouteStopListResponse = transport_schemas.RouteStopListResponse
TransportBoardingRecordResponse = transport_schemas.TransportBoardingRecordResponse
TransportBoardingRecordListResponse = transport_schemas.TransportBoardingRecordListResponse
LocationSampleResponse = transport_schemas.LocationSampleResponse
LocationSampleListResponse = transport_schemas.LocationSampleListResponse


class AdminTransportAssignmentCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    student_id: UUID
    route_id: UUID
    stop_id: UUID
    effective_from: date
    effective_to: date | None = None


class AdminTransportAssignmentUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    route_id: UUID | None = None
    stop_id: UUID | None = None
    effective_from: date | None = None
    effective_to: date | None = None


class AdminTransportAssignmentExpire(BaseModel):
    model_config = ConfigDict(extra="forbid")

    effective_to: date


class AdminTransportAttendantCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    user_id: UUID
    employee_code: str = Field(min_length=1, max_length=64)


class AdminTransportAttendantUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    employee_code: str | None = Field(default=None, min_length=1, max_length=64)


class AdminRouteCreate(transport_schemas.RouteCreate):
    model_config = ConfigDict(extra="forbid")


class AdminRouteUpdate(transport_schemas.RouteUpdate):
    model_config = ConfigDict(extra="forbid")


class AdminRouteStopCreate(transport_schemas.RouteStopCreate):
    model_config = ConfigDict(extra="forbid")


class OperationsOverviewResponse(BaseModel):
    active_buses: int
    active_trips: int
    active_transport_assignments: int
    active_card_assignments: int
    pending_card_assignments: int
    registered_cards: int
    blocked_cards: int
    rfid_events_last_24h: int
    boarding_events_last_24h: int
