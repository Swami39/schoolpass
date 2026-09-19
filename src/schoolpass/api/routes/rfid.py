from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from schoolpass.api.deps import Principal, get_session_factory, get_settings_dep, require
from schoolpass.config import Settings
from schoolpass.db.session import apply_tenant_context
from schoolpass.rfid import schemas as s
from schoolpass.rfid import services as svc
from schoolpass.tenancy.context import TenantContext

router = APIRouter(prefix="/api/v1", tags=["rfid"])


def _request_id(request: Request) -> str | None:
    return getattr(request.state, "request_id", None)


def _ctx(principal: Principal) -> TenantContext:
    return principal.context


@router.post("/rfid-readers", response_model=s.RfidReaderResponse)
async def create_reader(
    body: s.RfidReaderCreate,
    request: Request,
    principal: Annotated[Principal, Depends(require("rfid_readers:create"))],
    factory: Annotated[async_sessionmaker[AsyncSession], Depends(get_session_factory)],
) -> s.RfidReaderResponse:
    async with factory() as session:
        async with session.begin():
            await apply_tenant_context(session, _ctx(principal))
            row = await svc.create_reader(
                session,
                _ctx(principal),
                name=body.name,
                location=body.location,
                gate_id=body.gate_id,
                direction_mode=body.direction_mode,
                request_id=_request_id(request),
            )
    return s.RfidReaderResponse.model_validate(row, from_attributes=True)


@router.get("/rfid-readers", response_model=s.RfidReaderListResponse)
async def list_readers(
    principal: Annotated[Principal, Depends(require("rfid_readers:read"))],
    factory: Annotated[async_sessionmaker[AsyncSession], Depends(get_session_factory)],
) -> s.RfidReaderListResponse:
    async with factory() as session:
        async with session.begin():
            await apply_tenant_context(session, _ctx(principal))
            rows = await svc.list_readers(session, _ctx(principal))
    return s.RfidReaderListResponse(items=[s.RfidReaderResponse.model_validate(r, from_attributes=True) for r in rows])


@router.get("/rfid-readers/{reader_id}", response_model=s.RfidReaderResponse)
async def get_reader(
    reader_id: UUID,
    principal: Annotated[Principal, Depends(require("rfid_readers:read"))],
    factory: Annotated[async_sessionmaker[AsyncSession], Depends(get_session_factory)],
) -> s.RfidReaderResponse:
    async with factory() as session:
        async with session.begin():
            await apply_tenant_context(session, _ctx(principal))
            row = await svc.get_reader(session, _ctx(principal), reader_id)
    return s.RfidReaderResponse.model_validate(row, from_attributes=True)


@router.patch("/rfid-readers/{reader_id}", response_model=s.RfidReaderResponse)
async def patch_reader(
    reader_id: UUID,
    body: s.RfidReaderUpdate,
    request: Request,
    principal: Annotated[Principal, Depends(require("rfid_readers:update"))],
    factory: Annotated[async_sessionmaker[AsyncSession], Depends(get_session_factory)],
) -> s.RfidReaderResponse:
    async with factory() as session:
        async with session.begin():
            await apply_tenant_context(session, _ctx(principal))
            row = await svc.patch_reader(
                session,
                _ctx(principal),
                reader_id,
                name=body.name,
                location=body.location,
                gate_id=body.gate_id,
                direction_mode=body.direction_mode,
                status=body.status,
                request_id=_request_id(request),
            )
    return s.RfidReaderResponse.model_validate(row, from_attributes=True)


@router.post("/rfid-devices", response_model=s.RfidDeviceCreatedResponse)
async def create_device(
    body: s.RfidDeviceCreate,
    request: Request,
    principal: Annotated[Principal, Depends(require("rfid_devices:create"))],
    factory: Annotated[async_sessionmaker[AsyncSession], Depends(get_session_factory)],
    settings: Annotated[Settings, Depends(get_settings_dep)],
) -> s.RfidDeviceCreatedResponse:
    async with factory() as session:
        async with session.begin():
            await apply_tenant_context(session, _ctx(principal))
            device, secret = await svc.register_device(
                session,
                _ctx(principal),
                settings,
                device_id=body.device_id,
                reader_id=body.reader_id,
                device_name=body.device_name,
                request_id=_request_id(request),
            )
    data = s.RfidDeviceResponse.model_validate(device, from_attributes=True)
    return s.RfidDeviceCreatedResponse(**data.model_dump(), signing_secret=secret)


@router.get("/rfid-devices", response_model=s.RfidDeviceListResponse)
async def list_devices(
    principal: Annotated[Principal, Depends(require("rfid_devices:read"))],
    factory: Annotated[async_sessionmaker[AsyncSession], Depends(get_session_factory)],
) -> s.RfidDeviceListResponse:
    async with factory() as session:
        async with session.begin():
            await apply_tenant_context(session, _ctx(principal))
            rows = await svc.list_devices(session, _ctx(principal))
    return s.RfidDeviceListResponse(items=[s.RfidDeviceResponse.model_validate(r, from_attributes=True) for r in rows])


@router.get("/rfid-devices/{device_id}", response_model=s.RfidDeviceResponse)
async def get_device(
    device_id: UUID,
    principal: Annotated[Principal, Depends(require("rfid_devices:read"))],
    factory: Annotated[async_sessionmaker[AsyncSession], Depends(get_session_factory)],
) -> s.RfidDeviceResponse:
    async with factory() as session:
        async with session.begin():
            await apply_tenant_context(session, _ctx(principal))
            row = await svc.get_device(session, _ctx(principal), device_id)
    return s.RfidDeviceResponse.model_validate(row, from_attributes=True)


@router.patch("/rfid-devices/{device_id}", response_model=s.RfidDeviceResponse)
async def patch_device(
    device_id: UUID,
    body: s.RfidDeviceUpdate,
    request: Request,
    principal: Annotated[Principal, Depends(require("rfid_devices:update"))],
    factory: Annotated[async_sessionmaker[AsyncSession], Depends(get_session_factory)],
) -> s.RfidDeviceResponse:
    async with factory() as session:
        async with session.begin():
            await apply_tenant_context(session, _ctx(principal))
            row = await svc.patch_device(
                session,
                _ctx(principal),
                device_id,
                device_name=body.device_name,
                status=body.status,
                request_id=_request_id(request),
            )
    return s.RfidDeviceResponse.model_validate(row, from_attributes=True)


@router.post("/rfid-devices/{device_id}/keys/rotate", response_model=s.RfidDeviceKeyRotateResponse)
async def rotate_device_key(
    device_id: UUID,
    request: Request,
    principal: Annotated[Principal, Depends(require("rfid_devices:rotate_keys"))],
    factory: Annotated[async_sessionmaker[AsyncSession], Depends(get_session_factory)],
    settings: Annotated[Settings, Depends(get_settings_dep)],
) -> s.RfidDeviceKeyRotateResponse:
    async with factory() as session:
        async with session.begin():
            await apply_tenant_context(session, _ctx(principal))
            device, secret = await svc.rotate_device_key(
                session,
                _ctx(principal),
                settings,
                device_id,
                request_id=_request_id(request),
            )
    return s.RfidDeviceKeyRotateResponse(key_version=device.key_version, signing_secret=secret)
