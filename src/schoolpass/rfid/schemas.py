from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class RfidReaderCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    location: str | None = Field(default=None, max_length=255)
    gate_id: UUID | None = None
    direction_mode: str | None = Field(default=None, max_length=32)


class RfidReaderUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    location: str | None = Field(default=None, max_length=255)
    gate_id: UUID | None = None
    direction_mode: str | None = Field(default=None, max_length=32)
    status: str | None = None


class RfidReaderResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tenant_id: UUID
    name: str
    location: str | None
    gate_id: UUID | None
    direction_mode: str | None
    status: str
    created_at: datetime
    updated_at: datetime


class RfidReaderListResponse(BaseModel):
    items: list[RfidReaderResponse]


class RfidDeviceCreate(BaseModel):
    device_id: str = Field(min_length=1, max_length=128)
    reader_id: UUID
    device_name: str | None = Field(default=None, max_length=255)


class RfidDeviceUpdate(BaseModel):
    device_name: str | None = Field(default=None, max_length=255)
    status: str | None = None


class RfidDeviceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    device_id: str
    tenant_id: UUID
    reader_id: UUID
    key_version: int
    status: str
    device_name: str | None
    last_seen_at: datetime | None
    created_at: datetime
    updated_at: datetime


class RfidDeviceCreatedResponse(RfidDeviceResponse):
    signing_secret: str


class RfidDeviceListResponse(BaseModel):
    items: list[RfidDeviceResponse]


class RfidDeviceKeyRotateResponse(BaseModel):
    key_version: int
    signing_secret: str


class RfidEventPayload(BaseModel):
    device_event_id: str = Field(min_length=1, max_length=128)
    occurred_at: datetime
    hf_uid: str | None = None
    uhf_epc: str | None = None
    uhf_tid: str | None = None
    antenna: int | None = None
    rssi: float | None = None
    direction: str | None = Field(default=None, max_length=32)


class RfidIngestAcceptedResponse(BaseModel):
    status: str = "accepted"
    duplicate: bool = False
    event_id: UUID
    resolution_status: str | None = None


class RfidEventResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tenant_id: UUID
    reader_id: UUID
    device_uuid: UUID
    physical_card_id: UUID | None
    student_id: UUID | None
    hf_uid: str | None
    uhf_epc: str | None
    uhf_tid: str | None
    antenna: int | None
    rssi: float | None
    direction: str | None
    occurred_at: datetime
    received_at: datetime
    ingest_status: str
    processing_status: str | None = None
    resolution_status: str | None = None


class RfidEventListResponse(BaseModel):
    items: list[RfidEventResponse]
    next_cursor: str | None = None
