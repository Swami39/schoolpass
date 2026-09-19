from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class BusCreate(BaseModel):
    registration_number: str = Field(min_length=1, max_length=32)
    fleet_number: str | None = Field(default=None, max_length=32)
    display_name: str = Field(min_length=1, max_length=255)
    capacity: int = Field(gt=0)


class BusUpdate(BaseModel):
    registration_number: str | None = Field(default=None, min_length=1, max_length=32)
    fleet_number: str | None = Field(default=None, max_length=32)
    display_name: str | None = Field(default=None, min_length=1, max_length=255)
    capacity: int | None = Field(default=None, gt=0)


class BusResponse(BaseModel):
    id: UUID
    tenant_id: UUID
    registration_number: str
    fleet_number: str | None
    display_name: str
    capacity: int
    status: str
    created_at: datetime
    updated_at: datetime


class BusListResponse(BaseModel):
    items: list[BusResponse]
    next_cursor: str | None = None


class TransportAttendantCreate(BaseModel):
    user_id: UUID
    employee_code: str = Field(min_length=1, max_length=64)


class TransportAttendantUpdate(BaseModel):
    employee_code: str | None = Field(default=None, min_length=1, max_length=64)


class TransportAttendantResponse(BaseModel):
    id: UUID
    tenant_id: UUID
    user_id: UUID
    employee_code: str
    status: str
    created_at: datetime
    updated_at: datetime


class TransportAttendantListResponse(BaseModel):
    items: list[TransportAttendantResponse]
    next_cursor: str | None = None


class RouteCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    code: str = Field(min_length=1, max_length=64)
    direction: str = Field(pattern="^(pickup|dropoff)$")


class RouteUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    code: str | None = Field(default=None, min_length=1, max_length=64)
    direction: str | None = Field(default=None, pattern="^(pickup|dropoff)$")


class RouteResponse(BaseModel):
    id: UUID
    tenant_id: UUID
    name: str
    code: str
    direction: str
    status: str
    created_at: datetime
    updated_at: datetime


class RouteListResponse(BaseModel):
    items: list[RouteResponse]
    next_cursor: str | None = None


class RouteStopCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    sequence: int = Field(gt=0)
    latitude: Decimal = Field(ge=Decimal("-90"), le=Decimal("90"))
    longitude: Decimal = Field(ge=Decimal("-180"), le=Decimal("180"))
    geofence_radius_meters: int = Field(default=100, gt=0)


class RouteStopUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    sequence: int | None = Field(default=None, gt=0)
    latitude: Decimal | None = Field(default=None, ge=Decimal("-90"), le=Decimal("90"))
    longitude: Decimal | None = Field(default=None, ge=Decimal("-180"), le=Decimal("180"))
    geofence_radius_meters: int | None = Field(default=None, gt=0)


class RouteStopResponse(BaseModel):
    id: UUID
    tenant_id: UUID
    route_id: UUID
    name: str
    sequence: int
    latitude: Decimal
    longitude: Decimal
    geofence_radius_meters: int
    status: str
    created_at: datetime
    updated_at: datetime


class RouteStopListResponse(BaseModel):
    items: list[RouteStopResponse]


class RouteStopReorderRequest(BaseModel):
    stop_ids: list[UUID] = Field(min_length=1)

    @field_validator("stop_ids")
    @classmethod
    def unique_stop_ids(cls, value: list[UUID]) -> list[UUID]:
        if len(value) != len(set(value)):
            raise ValueError("stop_ids must not contain duplicates")
        return value


class TransportAssignmentCreate(BaseModel):
    student_id: UUID
    route_id: UUID
    stop_id: UUID
    effective_from: date
    effective_to: date | None = None


class TransportAssignmentUpdate(BaseModel):
    route_id: UUID | None = None
    stop_id: UUID | None = None
    effective_from: date | None = None
    effective_to: date | None = None


class TransportAssignmentExpireRequest(BaseModel):
    effective_to: date


class TransportAssignmentResponse(BaseModel):
    id: UUID
    tenant_id: UUID
    student_id: UUID
    route_id: UUID
    stop_id: UUID
    effective_from: date
    effective_to: date | None
    status: str
    created_at: datetime
    updated_at: datetime


class TransportAssignmentListResponse(BaseModel):
    items: list[TransportAssignmentResponse]
    next_cursor: str | None = None


class TripCreate(BaseModel):
    bus_id: UUID
    route_id: UUID
    attendant_id: UUID
    service_date: date
    shift: str = Field(pattern="^(pickup|dropoff)$")


class TripResponse(BaseModel):
    id: UUID
    tenant_id: UUID
    bus_id: UUID
    route_id: UUID
    attendant_id: UUID
    service_date: date
    shift: str
    status: str
    started_at: datetime | None
    ended_at: datetime | None
    created_at: datetime
    updated_at: datetime


class TripListResponse(BaseModel):
    items: list[TripResponse]
    next_cursor: str | None = None


class TransportNfcSyncRequest(BaseModel):
    client_event_id: UUID
    event_type: str = Field(pattern="^(boarding|dropoff)$")
    card_uid: str = Field(min_length=1, max_length=128)
    occurred_at: datetime
    device_sequence: int | None = Field(default=None, ge=0)
    trip_id: UUID
    trip_stop_id: UUID | None = None


class TransportNfcSyncResponse(BaseModel):
    result: str
    client_event_id: UUID
    server_event_id: UUID
    boarding_record_id: UUID | None
    occurred_at: datetime
    received_at: datetime
    rejection_code: str | None = None
    device_sequence: int | None = None


class TransportGpsSampleRequest(BaseModel):
    client_sample_id: UUID
    trip_id: UUID
    latitude: Decimal = Field(ge=Decimal("-90"), le=Decimal("90"))
    longitude: Decimal = Field(ge=Decimal("-180"), le=Decimal("180"))
    occurred_at: datetime
    bus_id: UUID | None = None
    accuracy_meters: Decimal | None = Field(default=None, ge=0)
    altitude_meters: Decimal | None = None
    speed_mps: Decimal | None = Field(default=None, ge=0)
    heading_degrees: Decimal | None = Field(default=None, ge=0, lt=Decimal("360"))
    device_sequence: int | None = Field(default=None, ge=0)
    source: str = Field(default="phone_gnss", pattern="^(phone_gnss|hardware_tracker)$")


class TransportGpsBatchSyncRequest(BaseModel):
    samples: list[TransportGpsSampleRequest] = Field(min_length=1, max_length=50)


class TransportGpsSampleSyncResult(BaseModel):
    result: str
    client_sample_id: UUID
    server_sample_id: UUID
    occurred_at: datetime
    received_at: datetime
    rejection_code: str | None = None
    device_sequence: int | None = None


class TransportGpsBatchSyncResponse(BaseModel):
    results: list[TransportGpsSampleSyncResult]


class LocationSampleResponse(BaseModel):
    id: UUID
    trip_id: UUID
    bus_id: UUID
    latitude: Decimal
    longitude: Decimal
    accuracy_meters: Decimal | None
    occurred_at: datetime
    received_at: datetime
    source: str


class LocationSampleListResponse(BaseModel):
    items: list[LocationSampleResponse]
