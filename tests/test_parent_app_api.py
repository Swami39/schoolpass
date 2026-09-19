"""Parent app API integration tests (Phase 8)."""

from __future__ import annotations

from datetime import date
from uuid import uuid4

import pytest

from fixtures_students import auth_headers
from notification_helpers import link_guardian_to_parent_user, parent_token
from parent_gps_helpers import ParentTransportWorld, build_parent_transport_world
from schoolpass.attendance.models import AttendanceRecord
from schoolpass.db.session import apply_tenant_context
from schoolpass.notifications.constants import NOTIFICATION_TYPE_SCHOOL_ENTRY
from schoolpass.notifications.service import build_idempotency_key, create_notification_with_outbox
from schoolpass.tenancy.context import TenantContext


@pytest.fixture
async def parent_world(db_factory, student_world, settings) -> ParentTransportWorld:
    return await build_parent_transport_world(db_factory, student_world, settings)


async def test_parent_lists_linked_children(client, parent_world) -> None:
    response = await client.get(
        "/api/v1/parent/children",
        headers=auth_headers(parent_world.parent_token),
    )
    assert response.status_code == 200
    body = response.json()
    ids = {item["id"] for item in body["items"]}
    assert str(parent_world.student_id) in ids
    assert str(parent_world.other_child_id) not in ids


async def test_parent_children_empty_without_guardian(client, student_world, settings, db_factory) -> None:
    linked = await link_guardian_to_parent_user(
        db_factory,
        tenant_id=student_world["tenant_a"],
        guardian_id=student_world["a_guardian_id"],
        student_id=student_world["a_student_id"],
        link_status="inactive",
    )
    token = parent_token(
        settings,
        user_id=linked["parent_user_id"],
        tenant_id=student_world["tenant_a"],
    )
    response = await client.get("/api/v1/parent/children", headers=auth_headers(token))
    assert response.status_code == 200
    assert response.json()["items"] == []


async def test_parent_attendance_requires_link(client, parent_world) -> None:
    denied = await client.get(
        f"/api/v1/parent/children/{parent_world.other_child_id}/attendance",
        headers=auth_headers(parent_world.parent_token),
    )
    assert denied.status_code == 404


async def test_parent_attendance_for_linked_child(client, parent_world, db_factory) -> None:
    async with db_factory() as session:
        async with session.begin():
            await apply_tenant_context(
                session,
                TenantContext(
                    actor_type="user",
                    tenant_id=parent_world.tenant_id,
                    user_id=parent_world.parent_user_id,
                ),
            )
            session.add(
                AttendanceRecord(
                    tenant_id=parent_world.tenant_id,
                    student_id=parent_world.student_id,
                    attendance_date=date.today(),
                    status="present",
                    entry_at=None,
                    exit_at=None,
                    source="rfid",
                    version=1,
                )
            )
    response = await client.get(
        f"/api/v1/parent/children/{parent_world.student_id}/attendance",
        headers=auth_headers(parent_world.parent_token),
    )
    assert response.status_code == 200
    items = response.json()["items"]
    assert len(items) == 1
    assert items[0]["student_id"] == str(parent_world.student_id)
    assert "tenant_id" not in items[0]


async def test_parent_notifications_inbox(client, parent_world, db_factory) -> None:
    async with db_factory() as session:
        async with session.begin():
            await apply_tenant_context(
                session,
                TenantContext(
                    actor_type="user",
                    tenant_id=parent_world.tenant_id,
                    user_id=parent_world.parent_user_id,
                ),
            )
            idem = build_idempotency_key(
                notification_type=NOTIFICATION_TYPE_SCHOOL_ENTRY,
                reference_id=uuid4(),
                recipient_user_id=parent_world.parent_user_id,
            )
            await create_notification_with_outbox(
                session,
                tenant_id=parent_world.tenant_id,
                recipient_user_id=parent_world.parent_user_id,
                notification_type=NOTIFICATION_TYPE_SCHOOL_ENTRY,
                title="Entry",
                body="Alex entered school",
                payload={"student_id": str(parent_world.student_id)},
                idempotency_key=idem,
            )
    listed = await client.get(
        "/api/v1/parent/notifications",
        headers=auth_headers(parent_world.parent_token),
    )
    assert listed.status_code == 200
    item = listed.json()["items"][0]
    assert item["notification_type"] == NOTIFICATION_TYPE_SCHOOL_ENTRY
    assert item["read"] is False
    assert "idempotency_key" not in item
    marked = await client.post(
        f"/api/v1/parent/notifications/{item['id']}/read",
        headers=auth_headers(parent_world.parent_token),
    )
    assert marked.status_code == 200
    assert marked.json()["read"] is True


async def test_parent_notification_preferences(client, parent_world) -> None:
    loaded = await client.get(
        "/api/v1/parent/notification-preferences",
        headers=auth_headers(parent_world.parent_token),
    )
    assert loaded.status_code == 200
    assert len(loaded.json()["items"]) == 5
    updated = await client.put(
        "/api/v1/parent/notification-preferences",
        headers=auth_headers(parent_world.parent_token),
        json={
            "items": [
                {"notification_type": "school_entry", "push_enabled": False},
            ],
        },
    )
    assert updated.status_code == 200
    school_entry = next(i for i in updated.json()["items"] if i["notification_type"] == "school_entry")
    assert school_entry["push_enabled"] is False
