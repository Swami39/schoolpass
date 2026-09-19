"""Adversarial security tests for teacher APIs (Phase 9)."""

from __future__ import annotations

from datetime import date, datetime, timezone
from uuid import uuid4

import pytest
from sqlalchemy import select

from fixtures_students import auth_headers
from schoolpass.db.session import apply_tenant_context
from schoolpass.people.models import FileMetadata
from schoolpass.teacher.models import TimetablePeriod
from schoolpass.tenancy.context import TenantContext
from parent_gps_helpers import ParentTransportWorld, build_parent_transport_world
from teacher_helpers import TeacherWorld, build_teacher_world


@pytest.fixture
async def teacher_world(db_factory, student_world, settings) -> TeacherWorld:
    return await build_teacher_world(db_factory, student_world, settings)


@pytest.fixture
async def parent_world(db_factory, student_world, settings) -> ParentTransportWorld:
    return await build_parent_transport_world(db_factory, student_world, settings)


async def test_tenant_a_teacher_cannot_list_tenant_b_classes(client, teacher_world, world, settings) -> None:
    from schoolpass.auth.tokens import encode_access_token

    token = encode_access_token(
        settings,
        user_id=teacher_world.teacher_user_id,
        tenant_id=world["tenant_b"],
        roles=["teacher"],
        mfa=False,
        platform=False,
    )
    response = await client.get("/api/v1/teacher/classes", headers=auth_headers(token))
    assert response.status_code in {403, 404}


async def test_tenant_a_teacher_cannot_read_tenant_b_students(
    client, teacher_world, student_world, world, settings
) -> None:
    from schoolpass.auth.tokens import encode_access_token

    token = encode_access_token(
        settings,
        user_id=teacher_world.teacher_user_id,
        tenant_id=world["tenant_b"],
        roles=["teacher"],
        mfa=False,
        platform=False,
    )
    response = await client.get(
        f"/api/v1/teacher/classes/{student_world['b_section_id']}/students",
        headers=auth_headers(token),
    )
    assert response.status_code in {403, 404}


async def test_unassigned_section_students_denied(client, teacher_world) -> None:
    response = await client.get(
        f"/api/v1/teacher/classes/{teacher_world.section_id}/students",
        headers=auth_headers(teacher_world.other_teacher_token),
    )
    assert response.status_code == 404


async def test_unassigned_section_attendance_write_denied(client, teacher_world) -> None:
    today = date.today().isoformat()
    response = await client.post(
        f"/api/v1/teacher/classes/{teacher_world.section_id}/attendance?date={today}",
        headers=auth_headers(teacher_world.other_teacher_token),
        json={"student_id": str(teacher_world.student_id), "status": "present"},
    )
    assert response.status_code == 404


async def test_other_teacher_cannot_patch_unassigned_timetable(client, teacher_world, db_factory) -> None:
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
            period_id = (
                await session.execute(
                    select(TimetablePeriod.id).where(
                        TimetablePeriod.tenant_id == teacher_world.tenant_id,
                        TimetablePeriod.teacher_user_id == teacher_world.teacher_user_id,
                    )
                )
            ).scalar_one()
    response = await client.patch(
        f"/api/v1/teacher/timetable/{period_id}",
        headers=auth_headers(teacher_world.other_teacher_token),
        json={},
    )
    assert response.status_code in {403, 404}


async def test_marks_outside_assigned_section_denied(client, teacher_world, student_world) -> None:
    response = await client.put(
        f"/api/v1/teacher/assessments/{teacher_world.assessment_id}/students/{student_world['b_student_id']}/marks",
        headers=auth_headers(teacher_world.teacher_token),
        json={"marks": 10},
    )
    assert response.status_code == 404


async def test_message_cannot_target_unassigned_student(client, teacher_world, student_world) -> None:
    response = await client.post(
        "/api/v1/teacher/messages",
        headers=auth_headers(teacher_world.teacher_token),
        json={
            "section_id": str(teacher_world.section_id),
            "student_id": str(student_world["b_student_id"]),
            "title": "Hi",
            "body": "Nope",
            "idempotency_key": f"sec-{uuid4()}",
        },
    )
    assert response.status_code == 404


async def test_cannot_use_other_tenant_file_attachment(client, teacher_world, db_factory, student_world) -> None:
    async with db_factory() as session:
        async with session.begin():
            await apply_tenant_context(
                session,
                TenantContext(
                    actor_type="user",
                    tenant_id=student_world["tenant_b"],
                    user_id=student_world["admin_b"],
                ),
            )
            row = FileMetadata(
                tenant_id=student_world["tenant_b"],
                purpose="teacher_message_image",
                blob_key=f"{student_world['tenant_b']}/teacher-messages/x.jpg",
                classification="SENSITIVE_CHILD_DATA",
                created_by=student_world["admin_b"],
            )
            session.add(row)
            await session.flush()
            other_file_id = row.id
    response = await client.post(
        "/api/v1/teacher/messages",
        headers=auth_headers(teacher_world.teacher_token),
        json={
            "section_id": str(teacher_world.section_id),
            "student_id": str(teacher_world.student_id),
            "title": "Hi",
            "body": "Image",
            "idempotency_key": f"file-{uuid4()}",
            "image_file_id": str(other_file_id),
        },
    )
    assert response.status_code == 404


async def test_nfc_duplicate_client_event_idempotent(client, teacher_world) -> None:
    event_id = uuid4()
    headers = {
        **auth_headers(teacher_world.teacher_token),
        "x-client-device-id": str(teacher_world.client_device_id),
    }
    payload = {
        "client_event_id": str(event_id),
        "section_id": str(teacher_world.section_id),
        "card_uid": teacher_world.card_hf_uid,
        "occurred_at": datetime.now(timezone.utc).isoformat(),
    }
    first = await client.post("/api/v1/teacher/nfc/events/sync", headers=headers, json=payload)
    second = await client.post("/api/v1/teacher/nfc/events/sync", headers=headers, json=payload)
    assert first.status_code == 200
    assert second.status_code == 200
    assert second.json()["result"] == "duplicate"


async def test_nfc_wrong_section_rejected(client, teacher_world) -> None:
    fake_section = uuid4()
    response = await client.post(
        "/api/v1/teacher/nfc/events/sync",
        headers={
            **auth_headers(teacher_world.teacher_token),
            "x-client-device-id": str(teacher_world.client_device_id),
        },
        json={
            "client_event_id": str(uuid4()),
            "section_id": str(fake_section),
            "card_uid": teacher_world.card_hf_uid,
            "occurred_at": datetime.now(timezone.utc).isoformat(),
        },
    )
    assert response.status_code == 404


async def test_other_teacher_cannot_write_marks(client, teacher_world) -> None:
    response = await client.put(
        f"/api/v1/teacher/assessments/{teacher_world.assessment_id}/students/{teacher_world.student_id}/marks",
        headers=auth_headers(teacher_world.other_teacher_token),
        json={"marks": 12},
    )
    assert response.status_code in {403, 404}


async def test_nfc_rejects_card_from_other_tenant(
    client, teacher_world, student_world, db_factory
) -> None:
    from datetime import datetime, timezone
    from schoolpass.cards.models import CardAssignment, PhysicalCard
    from schoolpass.db.session import apply_tenant_context
    from schoolpass.tenancy.context import TenantContext

    other_uid = f"HF-OTHER-{uuid4().hex[:8]}"
    async with db_factory() as session:
        async with session.begin():
            await apply_tenant_context(
                session,
                TenantContext(
                    actor_type="user",
                    tenant_id=student_world["tenant_b"],
                    user_id=student_world["admin_b"],
                ),
            )
            card = PhysicalCard(
                tenant_id=student_world["tenant_b"],
                hf_uid=other_uid,
                profile="uid_only",
                status="active",
            )
            session.add(card)
            await session.flush()
            issued = datetime(2025, 4, 1, tzinfo=timezone.utc)
            session.add(
                CardAssignment(
                    tenant_id=student_world["tenant_b"],
                    student_id=student_world["b_student_id"],
                    physical_card_id=card.id,
                    status="active",
                    issued_at=issued,
                    activated_at=issued,
                )
            )
    response = await client.post(
        "/api/v1/teacher/nfc/events/sync",
        headers={
            **auth_headers(teacher_world.teacher_token),
            "x-client-device-id": str(teacher_world.client_device_id),
        },
        json={
            "client_event_id": str(uuid4()),
            "section_id": str(teacher_world.section_id),
            "card_uid": other_uid,
            "occurred_at": datetime.now(timezone.utc).isoformat(),
        },
    )
    assert response.status_code == 200
    assert response.json()["result"] == "rejected"


async def test_notification_preference_tenant_isolation(client, parent_world, student_world, settings, db_factory) -> None:
    from schoolpass.auth.tokens import encode_access_token
    from schoolpass.notifications.preferences import set_push_preference

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
            await set_push_preference(
                session,
                tenant_id=parent_world.tenant_id,
                user_id=parent_world.parent_user_id,
                notification_type="teacher_message",
                push_enabled=False,
            )
    token_b = encode_access_token(
        settings,
        user_id=parent_world.parent_user_id,
        tenant_id=student_world["tenant_b"],
        roles=["parent"],
        mfa=False,
        platform=False,
    )
    response = await client.get(
        "/api/v1/parent/notification-preferences",
        headers=auth_headers(token_b),
    )
    assert response.status_code in {403, 404}
