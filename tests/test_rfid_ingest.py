from __future__ import annotations

import asyncio
import time
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from httpx import AsyncClient

from fixtures_students import auth_headers
from rfid_helpers import event_body, sign_rfid_ingest
from schoolpass.config import Settings
from schoolpass.db.session import apply_tenant_context, create_engine, session_factory
from schoolpass.rfid.models import RfidEvent
from schoolpass.tenancy.context import TenantContext


async def _provision_stack(client: AsyncClient, student_world: dict) -> dict:
    headers = auth_headers(student_world["token_a"])
    card = await client.post(
        "/api/v1/cards",
        json={"hf_uid": f"HF-{uuid4().hex[:8]}", "uhf_epc": f"E200{uuid4().hex[:8].upper()}", "profile": "uid_only"},
        headers=headers,
    )
    card_body = card.json()
    await client.post(f"/api/v1/cards/{card_body['id']}/activate", headers=headers)
    assignment = await client.post(
        "/api/v1/card-assignments",
        json={"student_id": str(student_world["a_student_id"]), "physical_card_id": card_body["id"]},
        headers=headers,
    )
    assignment_id = assignment.json()["id"]
    await client.post(f"/api/v1/card-assignments/{assignment_id}/activate", headers=headers)
    reader = await client.post("/api/v1/rfid-readers", headers=headers, json={"name": "Ingest Gate"})
    reader_id = reader.json()["id"]
    device_external = f"device-{uuid4().hex[:8]}"
    device = await client.post(
        "/api/v1/rfid-devices",
        headers=headers,
        json={"device_id": device_external, "reader_id": reader_id},
    )
    device_body = device.json()
    return {
        "headers": headers,
        "secret": device_body["signing_secret"],
        "device_external": device_external,
        "key_version": device_body["key_version"],
        "reader_id": reader_id,
        "card": card_body,
        "tenant_id": student_world["tenant_a"],
    }


async def _ingest(
    client: AsyncClient,
    stack: dict,
    *,
    device_event_id: str | None = None,
    occurred_at: datetime | None = None,
    nonce: str | None = None,
    extra_headers: dict[str, str] | None = None,
    body_overrides: dict | None = None,
    secret: str | None = None,
    key_version: int | None = None,
    device_external: str | None = None,
) -> tuple[int, dict]:
    occurred = occurred_at or datetime.now(tz=UTC)
    payload = {
        "device_event_id": device_event_id or f"evt-{uuid4().hex[:10]}",
        "occurred_at": occurred.isoformat(),
        "uhf_epc": stack["card"]["uhf_epc"],
        "hf_uid": stack["card"]["hf_uid"],
    }
    if body_overrides:
        payload.update(body_overrides)
    raw = event_body(**payload)
    headers = sign_rfid_ingest(
        secret=secret or stack["secret"],
        device_id=device_external or stack["device_external"],
        key_version=key_version or stack["key_version"],
        body=raw,
        nonce=nonce,
    )
    if extra_headers:
        headers.update(extra_headers)
    resp = await client.post("/ingest/v1/rfid/events", headers=headers, content=raw)
    return resp.status_code, resp.json()


@pytest.mark.asyncio
async def test_valid_signature_accepted(client: AsyncClient, student_world: dict) -> None:
    stack = await _provision_stack(client, student_world)
    status, body = await _ingest(client, stack)
    assert status == 200
    assert body["status"] == "accepted"
    assert body["duplicate"] is False
    assert body["resolution_status"] == "resolved"


@pytest.mark.asyncio
async def test_invalid_signature_rejected(client: AsyncClient, student_world: dict) -> None:
    stack = await _provision_stack(client, student_world)
    raw = event_body(
        device_event_id="evt-bad-sig",
        occurred_at=datetime.now(tz=UTC).isoformat(),
        uhf_epc=stack["card"]["uhf_epc"],
    )
    headers = sign_rfid_ingest(
        secret=stack["secret"],
        device_id=stack["device_external"],
        key_version=stack["key_version"],
        body=raw,
    )
    headers["X-Signature"] = "deadbeef"
    resp = await client.post("/ingest/v1/rfid/events", headers=headers, content=raw)
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "invalid_signature"


@pytest.mark.asyncio
async def test_unknown_device_rejected(client: AsyncClient, student_world: dict) -> None:
    stack = await _provision_stack(client, student_world)
    raw = event_body(
        device_event_id="evt-unknown-dev",
        occurred_at=datetime.now(tz=UTC).isoformat(),
        uhf_epc=stack["card"]["uhf_epc"],
    )
    headers = sign_rfid_ingest(
        secret=stack["secret"],
        device_id="unknown-device",
        key_version=1,
        body=raw,
    )
    resp = await client.post("/ingest/v1/rfid/events", headers=headers, content=raw)
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_replayed_nonce(client: AsyncClient, student_world: dict) -> None:
    stack = await _provision_stack(client, student_world)
    nonce = f"fixed-{uuid4().hex}"
    status1, _ = await _ingest(client, stack, nonce=nonce)
    assert status1 == 200
    raw = event_body(
        device_event_id=f"evt-{uuid4().hex[:8]}",
        occurred_at=datetime.now(tz=UTC).isoformat(),
        uhf_epc=stack["card"]["uhf_epc"],
    )
    headers = sign_rfid_ingest(
        secret=stack["secret"],
        device_id=stack["device_external"],
        key_version=stack["key_version"],
        body=raw,
        nonce=nonce,
    )
    resp = await client.post("/ingest/v1/rfid/events", headers=headers, content=raw)
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "replayed_request"


@pytest.mark.asyncio
async def test_duplicate_device_event_id(client: AsyncClient, student_world: dict) -> None:
    stack = await _provision_stack(client, student_world)
    event_id = "dup-event-001"
    status1, body1 = await _ingest(client, stack, device_event_id=event_id)
    assert status1 == 200
    status2, body2 = await _ingest(client, stack, device_event_id=event_id)
    assert status2 == 200
    assert body2["duplicate"] is True
    assert body2["event_id"] == body1["event_id"]


@pytest.mark.asyncio
async def test_occurred_at_and_received_at_differ(settings: Settings, client: AsyncClient, student_world: dict) -> None:
    stack = await _provision_stack(client, student_world)
    past = datetime.now(tz=UTC) - timedelta(hours=1)
    _, body = await _ingest(client, stack, occurred_at=past, device_event_id=f"clock-{uuid4().hex[:6]}")
    engine = create_engine(settings.database_url, null_pool=True)
    factory = session_factory(engine)
    async with factory() as session:
        async with session.begin():
            await apply_tenant_context(
                session,
                TenantContext(actor_type="user", tenant_id=stack["tenant_id"], user_id=uuid4()),
            )
            event = await session.get(RfidEvent, body["event_id"])
            assert event is not None
            assert event.occurred_at < event.received_at
    await engine.dispose()


@pytest.mark.asyncio
async def test_identifier_normalization_on_ingest(client: AsyncClient, student_world: dict) -> None:
    stack = await _provision_stack(client, student_world)
    raw = event_body(
        device_event_id=f"norm-{uuid4().hex[:6]}",
        occurred_at=datetime.now(tz=UTC).isoformat(),
        uhf_epc=f"  {stack['card']['uhf_epc'].lower()}  ",
    )
    headers = sign_rfid_ingest(
        secret=stack["secret"],
        device_id=stack["device_external"],
        key_version=stack["key_version"],
        body=raw,
    )
    resp = await client.post("/ingest/v1/rfid/events", headers=headers, content=raw)
    assert resp.status_code == 200
    assert resp.json()["resolution_status"] == "resolved"


@pytest.mark.asyncio
async def test_unknown_card_retained(client: AsyncClient, student_world: dict) -> None:
    stack = await _provision_stack(client, student_world)
    status, body = await _ingest(
        client,
        stack,
        device_event_id=f"unknown-{uuid4().hex[:6]}",
        body_overrides={"uhf_epc": "E200UNKNOWN0001", "hf_uid": None},
    )
    assert status == 200
    assert body["resolution_status"] == "unknown_card"


@pytest.mark.asyncio
async def test_tenant_isolation_rls(client: AsyncClient, student_world: dict, settings: Settings) -> None:
    stack_a = await _provision_stack(client, student_world)
    headers_b = auth_headers(student_world["token_b"])
    reader_b = await client.post("/api/v1/rfid-readers", headers=headers_b, json={"name": "B Gate"})
    await client.post(
        "/api/v1/rfid-devices",
        headers=headers_b,
        json={"device_id": f"b-{uuid4().hex[:6]}", "reader_id": reader_b.json()["id"]},
    )
    _, body_a = await _ingest(client, stack_a, device_event_id=f"rls-{uuid4().hex[:6]}")
    engine = create_engine(settings.database_url, null_pool=True)
    factory = session_factory(engine)
    async with factory() as session:
        async with session.begin():
            await apply_tenant_context(
                session,
                TenantContext(actor_type="user", tenant_id=student_world["tenant_b"], user_id=uuid4()),
            )
            hidden = await session.get(RfidEvent, body_a["event_id"])
            assert hidden is None
    await engine.dispose()


@pytest.mark.asyncio
async def test_concurrent_duplicate_events(client: AsyncClient, student_world: dict) -> None:
    stack = await _provision_stack(client, student_world)
    event_id = f"concurrent-{uuid4().hex[:8]}"

    async def send() -> tuple[int, dict]:
        return await _ingest(client, stack, device_event_id=event_id)

    results = await asyncio.gather(send(), send())
    statuses = [r[0] for r in results]
    assert all(s == 200 for s in statuses)
    event_ids = {r[1]["event_id"] for r in results}
    assert len(event_ids) == 1


@pytest.mark.asyncio
async def test_body_tampering_fails(client: AsyncClient, student_world: dict) -> None:
    stack = await _provision_stack(client, student_world)
    raw = event_body(
        device_event_id=f"tamper-{uuid4().hex[:6]}",
        occurred_at=datetime.now(tz=UTC).isoformat(),
        uhf_epc=stack["card"]["uhf_epc"],
    )
    headers = sign_rfid_ingest(
        secret=stack["secret"],
        device_id=stack["device_external"],
        key_version=stack["key_version"],
        body=raw,
    )
    tampered = raw.replace(stack["card"]["uhf_epc"].encode(), b"E200TAMPERED0001")
    resp = await client.post("/ingest/v1/rfid/events", headers=headers, content=tampered)
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_expired_timestamp(client: AsyncClient, student_world: dict) -> None:
    stack = await _provision_stack(client, student_world)
    raw = event_body(
        device_event_id=f"old-{uuid4().hex[:6]}",
        occurred_at=datetime.now(tz=UTC).isoformat(),
        uhf_epc=stack["card"]["uhf_epc"],
    )
    old_ts = str(int(time.time()) - 3600)
    headers = sign_rfid_ingest(
        secret=stack["secret"],
        device_id=stack["device_external"],
        key_version=stack["key_version"],
        body=raw,
        timestamp=int(old_ts),
    )
    resp = await client.post("/ingest/v1/rfid/events", headers=headers, content=raw)
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "expired_timestamp"
