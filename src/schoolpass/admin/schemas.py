from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from schoolpass.identity.models import Tenant


class SchoolProfileResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    legal_name: str
    display_name: str | None
    slug: str
    status: str
    timezone: str
    country: str
    contact_email: str | None
    contact_phone: str | None
    address_line1: str | None
    city: str | None
    state: str | None
    postal_code: str | None
    logo_file_id: UUID | None

    @classmethod
    def from_tenant(cls, tenant: Tenant) -> SchoolProfileResponse:
        return cls.model_validate(tenant)


class SchoolProfileUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    legal_name: str | None = Field(default=None, min_length=1, max_length=255)
    display_name: str | None = Field(default=None, max_length=255)
    timezone: str | None = Field(default=None, min_length=1, max_length=64)
    country: str | None = Field(default=None, min_length=2, max_length=2)
    contact_email: str | None = Field(default=None, max_length=255)
    contact_phone: str | None = Field(default=None, max_length=32)
    address_line1: str | None = Field(default=None, max_length=255)
    city: str | None = Field(default=None, max_length=128)
    state: str | None = Field(default=None, max_length=128)
    postal_code: str | None = Field(default=None, max_length=32)
    logo_file_id: UUID | None = None

    @field_validator("country")
    @classmethod
    def country_upper(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return value.upper()
