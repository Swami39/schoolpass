"""Enrollment tenant validation and historical integrity (Phase 10B hardening)."""

from __future__ import annotations

from datetime import date
from uuid import uuid4

import pytest
from sqlalchemy import func, select

from admin_helpers import AdminWorld, build_admin_world
from fixtures_students import auth_headers
from schoolpass.attendance.models import AttendanceRecord
from schoolpass.cards.models import CardAssignment
from schoolpass.db.session import apply_tenant_context
from schoolpass.people.models import Enrollment, SchoolClass, Section, Student, StudentGuardian
from schoolpass.teacher.models import Assessment
from schoolpass.tenancy.context import TenantContext
from teacher_helpers import TeacherWorld, build_teacher_world


@pytest.fixture
async def admin_world(db_factory, world, settings) -> AdminWorld:
    return await build_admin_world(db_factory, settings=settings, base_world=world)


@pytest.fixture
async def teacher_world(db_factory, student_world, settings) -> TeacherWorld:
    return await build_teacher_world(db_factory, student_world, settings)


def _enrollment_payload(student_world: dict, **overrides: object) -> dict:
    base = {
        "student_id": str(student_world["a_student_id"]),
        "academic_year_id": str(student_world["a_year_id"]),
        "class_id": str(student_world["a_class_id"]),
        "section_id": str(student_world["a_section_id"]),
        "starts_on": date.today().isoformat(),
    }
    base.update(overrides)
    return base


async def test_enrollment_cross_tenant_student(client, admin_world, student_world) -> None:
    response = await client.post(
        "/api/v1/admin/enrollments",
        headers=auth_headers(admin_world.admin_token),
        json=_enrollment_payload(student_world, student_id=str(student_world["b_student_id"])),
    )
    assert response.status_code == 404


async def test_enrollment_cross_tenant_academic_year(client, admin_world, student_world) -> None:
    response = await client.post(
        "/api/v1/admin/enrollments",
        headers=auth_headers(admin_world.admin_token),
        json=_enrollment_payload(student_world, academic_year_id=str(student_world["b_year_id"])),
    )
    assert response.status_code == 404


async def test_enrollment_cross_tenant_class(client, admin_world, student_world) -> None:
    response = await client.post(
        "/api/v1/admin/enrollments",
        headers=auth_headers(admin_world.admin_token),
        json=_enrollment_payload(
            student_world,
            class_id=str(student_world["b_class_id"]),
            section_id=str(student_world["a_section_id"]),
        ),
    )
    assert response.status_code == 404


async def test_enrollment_cross_tenant_section(client, admin_world, student_world) -> None:
    response = await client.post(
        "/api/v1/admin/enrollments",
        headers=auth_headers(admin_world.admin_token),
        json=_enrollment_payload(
            student_world,
            class_id=str(student_world["a_class_id"]),
            section_id=str(student_world["b_section_id"]),
        ),
    )
    assert response.status_code == 404


async def test_enrollment_section_wrong_class_same_tenant(
    client, admin_world, student_world, db_factory
) -> None:
    async with db_factory() as session:
        async with session.begin():
            await apply_tenant_context(
                session,
                TenantContext(actor_type="user", tenant_id=admin_world.tenant_id, user_id=admin_world.admin_user_id),
            )
            other_class = SchoolClass(tenant_id=admin_world.tenant_id, code="9", name="Class 9")
            session.add(other_class)
            await session.flush()
            other_section = Section(tenant_id=admin_world.tenant_id, class_id=other_class.id, name="B")
            session.add(other_section)
            await session.flush()
            other_section_id = other_section.id
    response = await client.post(
        "/api/v1/admin/enrollments",
        headers=auth_headers(admin_world.admin_token),
        json=_enrollment_payload(
            student_world,
            class_id=str(student_world["a_class_id"]),
            section_id=str(other_section_id),
        ),
    )
    assert response.status_code == 422


async def test_enrollment_patch_cross_tenant(client, admin_world, student_world, db_factory) -> None:
    async with db_factory() as session:
        async with session.begin():
            await apply_tenant_context(
                session,
                TenantContext(actor_type="user", tenant_id=student_world["tenant_b"], user_id=student_world["admin_b"]),
            )
            enrollment = Enrollment(
                tenant_id=student_world["tenant_b"],
                student_id=student_world["b_student_id"],
                academic_year_id=student_world["b_year_id"],
                class_id=student_world["b_class_id"],
                section_id=student_world["b_section_id"],
                starts_on=date(2025, 4, 1),
            )
            session.add(enrollment)
            await session.flush()
            enrollment_id = enrollment.id
    response = await client.patch(
        f"/api/v1/admin/enrollments/{enrollment_id}",
        headers=auth_headers(admin_world.admin_token),
        json={"status": "active"},
    )
    assert response.status_code == 404


async def test_enrollment_move_preserves_history_and_related_records(
    client, admin_world, teacher_world, student_world, db_factory
) -> None:
    student_id = teacher_world.student_id
    headers = auth_headers(admin_world.admin_token)

    async with db_factory() as session:
        async with session.begin():
            await apply_tenant_context(
                session,
                TenantContext(actor_type="user", tenant_id=admin_world.tenant_id, user_id=admin_world.admin_user_id),
            )
            session.add(
                AttendanceRecord(
                    tenant_id=admin_world.tenant_id,
                    student_id=student_id,
                    academic_year_id=teacher_world.year_id,
                    attendance_date=date(2025, 5, 1),
                    status="present",
                    source="manual",
                )
            )
            await session.flush()
            counts_before = {
                "attendance": await session.scalar(
                    select(func.count()).select_from(AttendanceRecord).where(AttendanceRecord.student_id == student_id)
                ),
                "cards": await session.scalar(
                    select(func.count()).select_from(CardAssignment).where(CardAssignment.student_id == student_id)
                ),
                "assessments": await session.scalar(
                    select(func.count()).select_from(Assessment).where(Assessment.tenant_id == admin_world.tenant_id)
                ),
                "guardians": await session.scalar(
                    select(func.count())
                    .select_from(StudentGuardian)
                    .where(StudentGuardian.student_id == student_id)
                ),
            }
            original_enrollment = (
                await session.execute(select(Enrollment).where(Enrollment.student_id == student_id))
            ).scalar_one()
            original_enrollment_id = original_enrollment.id
            original_section_id = original_enrollment.section_id

            clazz_b = SchoolClass(tenant_id=admin_world.tenant_id, code="7", name="Class 7")
            session.add(clazz_b)
            await session.flush()
            section_b = Section(tenant_id=admin_world.tenant_id, class_id=clazz_b.id, name="B")
            session.add(section_b)
            await session.flush()
            class_b_id = clazz_b.id
            section_b_id = section_b.id

    close = await client.post(
        f"/api/v1/admin/enrollments/{original_enrollment_id}/close",
        headers=headers,
        json={"ends_on": date(2025, 12, 31).isoformat(), "status": "completed"},
    )
    assert close.status_code == 200

    create = await client.post(
        "/api/v1/admin/enrollments",
        headers=headers,
        json={
            "student_id": str(student_id),
            "academic_year_id": str(teacher_world.year_id),
            "class_id": str(class_b_id),
            "section_id": str(section_b_id),
            "starts_on": date(2026, 1, 1).isoformat(),
        },
    )
    assert create.status_code == 200

    history = await client.get(f"/api/v1/admin/students/{student_id}/enrollments", headers=headers)
    assert history.status_code == 200
    items = history.json()["items"]
    assert len(items) >= 2
    enrollment_ids = {item["id"] for item in items}
    assert str(original_enrollment_id) in enrollment_ids
    assert str(original_section_id) in {item["section_id"] for item in items}
    assert str(section_b_id) in {item["section_id"] for item in items}

    active = [item for item in items if item["status"] == "active"]
    assert len(active) == 1
    assert active[0]["section_id"] == str(section_b_id)

    async with db_factory() as session:
        async with session.begin():
            await apply_tenant_context(
                session,
                TenantContext(actor_type="user", tenant_id=admin_world.tenant_id, user_id=admin_world.admin_user_id),
            )
            student = await session.get(Student, student_id)
            assert student is not None
            assert student.status == "active"
            assert counts_before["attendance"] == await session.scalar(
                select(func.count()).select_from(AttendanceRecord).where(AttendanceRecord.student_id == student_id)
            )
            assert counts_before["cards"] == await session.scalar(
                select(func.count()).select_from(CardAssignment).where(CardAssignment.student_id == student_id)
            )
            assert counts_before["assessments"] == await session.scalar(
                select(func.count()).select_from(Assessment).where(Assessment.tenant_id == admin_world.tenant_id)
            )
            assert counts_before["guardians"] == await session.scalar(
                select(func.count())
                .select_from(StudentGuardian)
                .where(StudentGuardian.student_id == student_id)
            )

    # In-place PATCH move updates the same row; close+create preserves prior enrollment row.
    move = await client.patch(
        f"/api/v1/admin/enrollments/{create.json()['id']}",
        headers=headers,
        json={"class_id": str(student_world["a_class_id"]), "section_id": str(student_world["a_section_id"])},
    )
    assert move.status_code == 200
    still_two_rows = await client.get(f"/api/v1/admin/students/{student_id}/enrollments", headers=headers)
    assert len(still_two_rows.json()["items"]) >= 2


async def test_list_enrollments_filter_by_section(client, admin_world, student_world) -> None:
    headers = auth_headers(admin_world.admin_token)

    created = await client.post(
        "/api/v1/admin/enrollments",
        headers=headers,
        json=_enrollment_payload(student_world),
    )
    assert created.status_code == 200

    # A second, empty section in the same class.
    section_b = await client.post(
        "/api/v1/admin/sections",
        headers=headers,
        json={"class_id": str(student_world["a_class_id"]), "name": "B"},
    )
    assert section_b.status_code == 200
    section_b_id = section_b.json()["id"]

    filtered = await client.get(
        f"/api/v1/admin/enrollments?section_id={student_world['a_section_id']}",
        headers=headers,
    )
    assert filtered.status_code == 200
    items = filtered.json()["items"]
    assert len(items) >= 1
    assert all(item["section_id"] == str(student_world["a_section_id"]) for item in items)

    empty = await client.get(
        f"/api/v1/admin/enrollments?section_id={section_b_id}",
        headers=headers,
    )
    assert empty.status_code == 200
    assert empty.json()["items"] == []

    # A section from another tenant must not leak through the filter.
    cross_tenant = await client.get(
        f"/api/v1/admin/enrollments?section_id={student_world['b_section_id']}",
        headers=headers,
    )
    assert cross_tenant.status_code == 404

    # Unknown section ids are rejected, not silently ignored.
    missing = await client.get(
        f"/api/v1/admin/enrollments?section_id={uuid4()}",
        headers=headers,
    )
    assert missing.status_code == 404
