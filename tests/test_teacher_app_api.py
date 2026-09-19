"""Teacher app API integration tests (Phase 9)."""

from __future__ import annotations

from datetime import date, datetime, timezone
from uuid import uuid4

import pytest
from sqlalchemy import select

from fixtures_students import auth_headers
from schoolpass.identity.models import OutboxEvent, TenantMembership
from schoolpass.notifications.models import Notification
from teacher_helpers import TeacherWorld, build_teacher_world


@pytest.fixture
async def teacher_world(db_factory, student_world, settings) -> TeacherWorld:
    return await build_teacher_world(db_factory, student_world, settings)


async def test_teacher_lists_assigned_classes(client, teacher_world) -> None:
    response = await client.get("/api/v1/teacher/classes", headers=auth_headers(teacher_world.teacher_token))
    assert response.status_code == 200
    items = response.json()["items"]
    assert len(items) == 1
    assert items[0]["section_id"] == str(teacher_world.section_id)


async def test_teacher_cannot_access_unassigned_section(client, teacher_world) -> None:
    denied = await client.get(
        f"/api/v1/teacher/classes/{teacher_world.section_id}/students",
        headers=auth_headers(teacher_world.other_teacher_token),
    )
    assert denied.status_code == 404


async def test_teacher_lists_students(client, teacher_world) -> None:
    response = await client.get(
        f"/api/v1/teacher/classes/{teacher_world.section_id}/students",
        headers=auth_headers(teacher_world.teacher_token),
    )
    assert response.status_code == 200
    ids = {item["id"] for item in response.json()["items"]}
    assert str(teacher_world.student_id) in ids


async def test_teacher_marks_attendance(client, teacher_world) -> None:
    today = date.today().isoformat()
    response = await client.post(
        f"/api/v1/teacher/classes/{teacher_world.section_id}/attendance?date={today}",
        headers=auth_headers(teacher_world.teacher_token),
        json={"student_id": str(teacher_world.student_id), "status": "present"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "present"
    assert body["source"] == "manual_teacher"


async def test_teacher_cross_tenant_forbidden(client, teacher_world, db_factory, world, settings) -> None:
    from schoolpass.auth.tokens import encode_access_token

    token_b = encode_access_token(
        settings,
        user_id=teacher_world.teacher_user_id,
        tenant_id=world["tenant_b"],
        roles=["teacher"],
        mfa=False,
        platform=False,
    )
    response = await client.get("/api/v1/teacher/classes", headers=auth_headers(token_b))
    assert response.status_code in {403, 404}


async def test_inactive_teacher_rejected(client, teacher_world, db_factory) -> None:
    from schoolpass.db.session import apply_tenant_context
    from schoolpass.tenancy.context import TenantContext

    async with db_factory() as session:
        async with session.begin():
            await apply_tenant_context(
                session,
                TenantContext(
                    actor_type="user",
                    tenant_id=teacher_world.tenant_id,
                    user_id=teacher_world.teacher_user_id,
                ),
            )
            membership = (
                await session.execute(
                    select(TenantMembership).where(
                        TenantMembership.tenant_id == teacher_world.tenant_id,
                        TenantMembership.user_id == teacher_world.teacher_user_id,
                    )
                )
            ).scalar_one()
            membership.status = "inactive"
    response = await client.get("/api/v1/teacher/classes", headers=auth_headers(teacher_world.teacher_token))
    assert response.status_code == 403


async def test_teacher_nfc_valid_card(client, teacher_world) -> None:
    response = await client.post(
        "/api/v1/teacher/nfc/events/sync",
        headers={
            **auth_headers(teacher_world.teacher_token),
            "x-client-device-id": str(teacher_world.client_device_id),
        },
        json={
            "client_event_id": str(uuid4()),
            "section_id": str(teacher_world.section_id),
            "card_uid": teacher_world.card_hf_uid,
            "occurred_at": datetime.now(timezone.utc).isoformat(),
        },
    )
    assert response.status_code == 200
    assert response.json()["result"] == "processed"


async def test_teacher_nfc_wrong_class(client, teacher_world, student_world) -> None:
    response = await client.post(
        "/api/v1/teacher/nfc/events/sync",
        headers={
            **auth_headers(teacher_world.teacher_token),
            "x-client-device-id": str(teacher_world.client_device_id),
        },
        json={
            "client_event_id": str(uuid4()),
            "section_id": str(student_world["b_section_id"]),
            "card_uid": teacher_world.card_hf_uid,
            "occurred_at": datetime.now(timezone.utc).isoformat(),
        },
    )
    assert response.status_code in {404, 200}
    if response.status_code == 200:
        assert response.json()["result"] == "rejected"


async def test_teacher_results_write(client, teacher_world) -> None:
    response = await client.put(
        f"/api/v1/teacher/assessments/{teacher_world.assessment_id}/students/{teacher_world.student_id}/marks",
        headers=auth_headers(teacher_world.teacher_token),
        json={"marks": 42},
    )
    assert response.status_code == 200
    assert response.json()["marks"] == 42


async def test_teacher_results_invalid_marks(client, teacher_world) -> None:
    response = await client.put(
        f"/api/v1/teacher/assessments/{teacher_world.assessment_id}/students/{teacher_world.student_id}/marks",
        headers=auth_headers(teacher_world.teacher_token),
        json={"marks": 500},
    )
    assert response.status_code == 422


async def test_teacher_message_creates_parent_notification(client, teacher_world, db_factory) -> None:
    idem = f"teacher-msg-{uuid4()}"
    response = await client.post(
        "/api/v1/teacher/messages",
        headers=auth_headers(teacher_world.teacher_token),
        json={
            "section_id": str(teacher_world.section_id),
            "student_id": str(teacher_world.student_id),
            "title": "Urgent",
            "body": "Please contact school",
            "urgent": True,
            "idempotency_key": idem,
        },
    )
    assert response.status_code == 200
    assert response.json()["recipient_count"] >= 1
    from schoolpass.db.session import apply_tenant_context
    from schoolpass.tenancy.context import TenantContext

    async with db_factory() as session:
        await apply_tenant_context(
            session,
            TenantContext(
                actor_type="user",
                tenant_id=teacher_world.tenant_id,
                user_id=teacher_world.teacher_user_id,
            ),
        )
        notif = (
            await session.execute(
                select(Notification).where(
                    Notification.tenant_id == teacher_world.tenant_id,
                    Notification.recipient_user_id == teacher_world.parent_user_id,
                )
            )
        ).scalar_one_or_none()
        assert notif is not None
        outbox = (
            await session.execute(
                select(OutboxEvent).where(OutboxEvent.topic == "notification.dispatch")
            )
        ).scalars().first()
        assert outbox is not None
