from __future__ import annotations

from datetime import date
from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy import select, text
from sqlalchemy.exc import DBAPIError

from fixtures_students import auth_headers
from schoolpass.db.session import apply_tenant_context
from schoolpass.identity.models import AuditLog, OutboxEvent
from schoolpass.people.models import Enrollment, StudentGuardian
from schoolpass.tenancy.context import TenantContext


async def test_create_and_get_student(client: AsyncClient, student_world: dict) -> None:
    payload = {
        "admission_no": f"ADM-{uuid4().hex[:6]}",
        "first_name": "Test",
        "last_name": "Learner",
        "date_of_birth": "2015-06-01",
    }
    created = await client.post(
        "/api/v1/students",
        json=payload,
        headers=auth_headers(student_world["token_a"]),
    )
    assert created.status_code == 200
    body = created.json()
    assert body["historical_subject_id"]
    assert body["tenant_id"] == str(student_world["tenant_a"])

    fetched = await client.get(
        f"/api/v1/students/{body['id']}",
        headers=auth_headers(student_world["token_a"]),
    )
    assert fetched.status_code == 200
    assert fetched.json()["admission_no"] == payload["admission_no"]


async def test_teacher_cannot_create_student(client: AsyncClient, world: dict) -> None:
    login = await client.post(
        "/api/v1/auth/password/login",
        json={"identifier": world["email_a"], "password": "correct-horse-battery"},
    )
    token = login.json()["access_token"]
    response = await client.post(
        "/api/v1/students",
        json={"admission_no": "X-1", "first_name": "Nope", "last_name": "Denied"},
        headers=auth_headers(token),
    )
    assert response.status_code == 403


async def test_cross_tenant_student_read_is_not_found(client: AsyncClient, student_world: dict) -> None:
    response = await client.get(
        f"/api/v1/students/{student_world['a_student_id']}",
        headers=auth_headers(student_world["token_b"]),
    )
    assert response.status_code == 404


async def test_guardian_link_and_duplicate_rejected(client: AsyncClient, student_world: dict) -> None:
    headers = auth_headers(student_world["token_a"])
    link = await client.post(
        f"/api/v1/students/{student_world['a_student_id']}/guardians",
        json={
            "guardian_id": str(student_world["a_guardian_id"]),
            "relationship_type": "guardian",
            "is_primary_contact": True,
        },
        headers=headers,
    )
    assert link.status_code == 200
    dup = await client.post(
        f"/api/v1/students/{student_world['a_student_id']}/guardians",
        json={"guardian_id": str(student_world["a_guardian_id"]), "relationship_type": "guardian"},
        headers=headers,
    )
    assert dup.status_code == 409


async def test_enrollment_history_and_close(client: AsyncClient, student_world: dict) -> None:
    headers = auth_headers(student_world["token_a"])
    create = await client.post(
        "/api/v1/enrollments",
        json={
            "student_id": str(student_world["a_student_id"]),
            "academic_year_id": str(student_world["a_year_id"]),
            "class_id": str(student_world["a_class_id"]),
            "section_id": str(student_world["a_section_id"]),
            "starts_on": "2025-04-01",
        },
        headers=headers,
    )
    assert create.status_code == 200
    enrollment_id = create.json()["id"]
    closed = await client.post(
        f"/api/v1/enrollments/{enrollment_id}/close",
        json={"ends_on": "2026-03-31", "status": "completed"},
        headers=headers,
    )
    assert closed.status_code == 200
    history = await client.get(
        f"/api/v1/students/{student_world['a_student_id']}/enrollments",
        headers=headers,
    )
    assert history.status_code == 200
    assert len(history.json()["items"]) >= 1


async def test_student_lifecycle_and_audit(client: AsyncClient, student_world: dict, db_factory) -> None:
    headers = auth_headers(student_world["token_a"])
    student_id = student_world["a_student_id"]
    withdrawn = await client.post(f"/api/v1/students/{student_id}/withdraw", headers=headers)
    assert withdrawn.status_code == 200
    assert withdrawn.json()["status"] == "withdrawn"

    hidden = await client.post(f"/api/v1/students/{student_id}/hide", headers=headers)
    assert hidden.status_code == 200
    assert hidden.json()["pii_state"] == "hidden"

    listed = await client.get("/api/v1/students", headers=headers)
    assert all(item["id"] != str(student_id) for item in listed.json()["items"])

    anonymized = await client.post(f"/api/v1/students/{student_id}/anonymize", headers=headers)
    assert anonymized.status_code == 200
    body = anonymized.json()
    assert body["pii_state"] == "anonymized"
    assert body["first_name"] == "Former"
    assert body["historical_subject_id"]

    async with db_factory() as session:
        async with session.begin():
            await apply_tenant_context(
                session,
                TenantContext(
                    actor_type="user",
                    tenant_id=student_world["tenant_a"],
                    user_id=student_world["admin_a"],
                ),
            )
            audit = (
                await session.execute(
                    select(AuditLog).where(
                        AuditLog.resource_id == student_id,
                        AuditLog.action == "student.anonymized",
                    )
                )
            ).scalar_one_or_none()
            assert audit is not None
            assert "password" not in audit.metadata_
            outbox = (
                await session.execute(
                    select(OutboxEvent).where(
                        OutboxEvent.topic == "student.anonymized",
                        OutboxEvent.payload["student_id"].astext == str(student_id),
                    )
                )
            ).scalar_one_or_none()
            assert outbox is not None
            assert "first_name" not in outbox.payload


async def test_rls_force_on_student_tables(engine) -> None:
    async with engine.connect() as conn:
        for table in ("students", "guardians", "student_guardians", "enrollments"):
            row = (
                await conn.execute(
                    text(
                        """
                        SELECT relrowsecurity, relforcerowsecurity
                        FROM pg_class WHERE relname = :table
                        """
                    ),
                    {"table": table},
                )
            ).one()
            assert row[0] is True and row[1] is True


async def test_cross_tenant_guardian_link_fails(db_factory, student_world) -> None:
    async with db_factory() as session:
        async with session.begin():
            await apply_tenant_context(
                session,
                TenantContext(
                    actor_type="user",
                    tenant_id=student_world["tenant_a"],
                    user_id=student_world["admin_a"],
                ),
            )
            session.add(
                StudentGuardian(
                    tenant_id=student_world["tenant_a"],
                    student_id=student_world["a_student_id"],
                    guardian_id=student_world["b_guardian_id"],
                    relationship_type="guardian",
                )
            )
            with pytest.raises(DBAPIError):
                await session.flush()


async def test_cross_tenant_enrollment_class_fails(db_factory, student_world) -> None:
    async with db_factory() as session:
        async with session.begin():
            await apply_tenant_context(
                session,
                TenantContext(
                    actor_type="user",
                    tenant_id=student_world["tenant_a"],
                    user_id=student_world["admin_a"],
                ),
            )
            session.add(
                Enrollment(
                    tenant_id=student_world["tenant_a"],
                    student_id=student_world["a_student_id"],
                    academic_year_id=student_world["a_year_id"],
                    class_id=student_world["b_class_id"],
                    section_id=student_world["a_section_id"],
                    starts_on=date(2025, 4, 1),
                )
            )
            with pytest.raises(DBAPIError):
                await session.flush()
