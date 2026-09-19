from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, Field

from schoolpass.notifications.models import NotificationDevice


class RegisterPushDeviceRequest(BaseModel):
    platform: str = Field(min_length=2, max_length=32)
    fcm_token: str = Field(min_length=8, max_length=512)


class PushDeviceResponse(BaseModel):
    id: UUID
    platform: str
    status: str

    @classmethod
    def from_device(cls, device: NotificationDevice) -> PushDeviceResponse:
        return cls(id=device.id, platform=device.platform, status=device.status)
