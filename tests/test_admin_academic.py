"""Admin academic structure API tests (Phase 10.2)."""

from __future__ import annotations

from uuid import uuid4

import pytest
from sqlalchemy import func, select

from admin_helpers import AdminWorld, build_admin_world
from fixtures_students import auth_headers
from schoolpass.auth.tokens import encode_access_token
from schoolpass.db.session import apply_tenant_context
from schoolpass.identity.models import AuditLog, StaffProfile, TenantMembership
from schoolpass.people.models import SchoolClass, Student
from schoolpass.teacher.models import Subject
from schoolpass.tenancy.context import TenantContext
from teacher_helpers import TeacherWorld, build_teacher_world


@pytest.fixture
async def admin_world(db_factory, world, settings) -> AdminWorld:
    return await build_admin_world(db_factory, settings=settings, base_world=world)


@pytest.fixture
async def teacher_world(db_factory, student_world, settings) -> TeacherWorld:
    return await build_teacher_world(db_factory, student_world, settings)


async def test_admin_can_list_academic_structure(client, admin_world, student_world) -> None:
    years = await client.get("/api/v1/admin/academic-years", headers=auth_headers(admin_world.admin_token))
    assert years.status_code == 200
    assert any(item["id"] == str(student_world["a_year_id"]) for item in years.json()["items"])
    classes = await client.get("/api/v1/admin/classes", headers=auth_headers(admin_world.admin_token))
    assert classes.status_code == 200
    sections = await client.get(
        f"/api/v1/admin/sections?class_id={student_world['a_class_id']}",
        headers=auth_headers(admin_world.admin_token),
    )
    assert sections.status_code == 200


async def test_unauthenticated_rejected(client) -> None:
    assert (await client.get("/api/v1/admin/academic-years")).status_code == 401


async def test_inactive_membership_rejected(client, db_factory, admin_world, settings) -> None:
    async with db_factory() as session:
        async with session.begin():
            await apply_tenant_context(
                session,
                TenantContext(actor_type="user", tenant_id=admin_world.tenant_id, user_id=admin_world.admin_user_id),
            )
            membership = (
                await session.execute(
                    select(TenantMembership).where(
                        TenantMembership.user_id == admin_world.admin_user_id,
                        TenantMembership.tenant_id == admin_world.tenant_id,
                    )
                )
            ).scalar_one()
            membership.status = "suspended"
    token = encode_access_token(
        settings,
        user_id=admin_world.admin_user_id,
        tenant_id=admin_world.tenant_id,
        roles=["school_admin"],
        mfa=False,
        platform=False,
    )
    assert (await client.get("/api/v1/admin/classes", headers=auth_headers(token))).status_code == 403


async def test_teacher_cannot_write_academic(client, admin_world) -> None:
    response = await client.post(
        "/api/v1/admin/classes",
        headers=auth_headers(admin_world.teacher_token),
        json={"code": "X", "name": "Class X"},
    )
    assert response.status_code == 403


async def test_academic_lists_exclude_other_tenant_rows(client, admin_world, student_world) -> None:
    years = await client.get("/api/v1/admin/academic-years", headers=auth_headers(admin_world.admin_token))
    year_ids = {item["id"] for item in years.json()["items"]}
    assert str(student_world["a_year_id"]) in year_ids
    assert str(student_world["b_year_id"]) not in year_ids

    classes = await client.get("/api/v1/admin/classes", headers=auth_headers(admin_world.admin_token))
    class_ids = {item["id"] for item in classes.json()["items"]}
    assert str(student_world["a_class_id"]) in class_ids
    assert str(student_world["b_class_id"]) not in class_ids


async def test_cannot_patch_other_tenant_class_with_own_tenant_jwt(
    client, admin_world, student_world, db_factory
) -> None:
    response = await client.patch(
        f"/api/v1/admin/classes/{student_world['b_class_id']}",
        headers=auth_headers(admin_world.admin_token),
        json={"name": "Stolen Name"},
    )
    assert response.status_code == 404
    async with db_factory() as session:
        async with session.begin():
            await apply_tenant_context(
                session,
                TenantContext(actor_type="user", tenant_id=student_world["tenant_b"], user_id=student_world["admin_b"]),
            )
            south = await session.get(SchoolClass, student_world["b_class_id"])
            assert south is not None
            assert south.name == "Class 8"


async def test_cross_tenant_read_denied(client, admin_world, settings) -> None:
    token = encode_access_token(
        settings,
        user_id=admin_world.admin_user_id,
        tenant_id=admin_world.other_tenant_id,
        roles=["school_admin"],
        mfa=False,
        platform=False,
    )
    assert (await client.get("/api/v1/admin/subjects", headers=auth_headers(token))).status_code == 403


async def test_cross_tenant_patch_denied(client, admin_world, settings, student_world) -> None:
    token = encode_access_token(
        settings,
        user_id=admin_world.admin_user_id,
        tenant_id=admin_world.other_tenant_id,
        roles=["school_admin"],
        mfa=False,
        platform=False,
    )
    response = await client.patch(
        f"/api/v1/admin/classes/{student_world['b_class_id']}",
        headers=auth_headers(token),
        json={"name": "Hacked"},
    )
    assert response.status_code == 403


async def test_tenant_id_in_body_rejected(client, admin_world) -> None:
    response = await client.post(
        "/api/v1/admin/academic-years",
        headers=auth_headers(admin_world.admin_token),
        json={
            "code": "2026-27",
            "name": "Year 2026-27",
            "starts_on": "2026-04-01",
            "ends_on": "2027-03-31",
            "tenant_id": str(admin_world.other_tenant_id),
        },
    )
    assert response.status_code == 422


async def test_create_academic_year(client, admin_world) -> None:
    response = await client.post(
        "/api/v1/admin/academic-years",
        headers=auth_headers(admin_world.admin_token),
        json={
            "code": "2027-28",
            "name": "Academic 2027-28",
            "starts_on": "2027-04-01",
            "ends_on": "2028-03-31",
        },
    )
    assert response.status_code == 200
    assert response.json()["code"] == "2027-28"


async def test_invalid_academic_year_dates_rejected(client, admin_world) -> None:
    bad = await client.post(
        "/api/v1/admin/academic-years",
        headers=auth_headers(admin_world.admin_token),
        json={
            "code": "bad",
            "name": "Bad",
            "starts_on": "2027-04-01",
            "ends_on": "2027-03-01",
        },
    )
    assert bad.status_code == 422


async def test_duplicate_academic_year_code_conflict(client, admin_world, student_world) -> None:
    response = await client.post(
        "/api/v1/admin/academic-years",
        headers=auth_headers(admin_world.admin_token),
        json={
            "code": "2025-26",
            "name": "Duplicate",
            "starts_on": "2025-04-01",
            "ends_on": "2026-03-31",
        },
    )
    assert response.status_code == 409


async def test_create_class_and_section(client, admin_world) -> None:
    clazz = await client.post(
        "/api/v1/admin/classes",
        headers=auth_headers(admin_world.admin_token),
        json={"code": "9", "name": "Class 9"},
    )
    assert clazz.status_code == 200
    class_id = clazz.json()["id"]
    section = await client.post(
        "/api/v1/admin/sections",
        headers=auth_headers(admin_world.admin_token),
        json={"class_id": class_id, "name": "B"},
    )
    assert section.status_code == 200
    assert section.json()["class_id"] == class_id


async def test_section_cannot_reference_other_tenant_class(
    client, admin_world, student_world
) -> None:
    response = await client.post(
        "/api/v1/admin/sections",
        headers=auth_headers(admin_world.admin_token),
        json={"class_id": str(student_world["b_class_id"]), "name": "Z"},
    )
    assert response.status_code == 404


async def test_deactivate_class_preserves_enrollment(
    client, admin_world, student_world, db_factory
) -> None:
    response = await client.patch(
        f"/api/v1/admin/classes/{student_world['a_class_id']}",
        headers=auth_headers(admin_world.admin_token),
        json={"status": "inactive"},
    )
    assert response.status_code == 200
    async with db_factory() as session:
        async with session.begin():
            await apply_tenant_context(
                session,
                TenantContext(actor_type="user", tenant_id=admin_world.tenant_id, user_id=admin_world.admin_user_id),
            )
            student = await session.get(Student, student_world["a_student_id"])
            assert student is not None
            assert student.status == "active"


async def test_create_subject_and_duplicate(client, admin_world, teacher_world) -> None:
    created = await client.post(
        "/api/v1/admin/subjects",
        headers=auth_headers(admin_world.admin_token),
        json={"code": "SCI", "name": "Science"},
    )
    assert created.status_code == 200
    dup = await client.post(
        "/api/v1/admin/subjects",
        headers=auth_headers(admin_world.admin_token),
        json={"code": "MATH", "name": "Duplicate Math"},
    )
    assert dup.status_code == 409


async def test_cross_tenant_subject_on_assignment_rejected(
    client, admin_world, student_world, teacher_world, db_factory
) -> None:
    async with db_factory() as session:
        async with session.begin():
            await apply_tenant_context(
                session,
                TenantContext(actor_type="user", tenant_id=student_world["tenant_b"], user_id=student_world["admin_b"]),
            )
            other_subject = Subject(tenant_id=student_world["tenant_b"], code="OTHER", name="Other")
            session.add(other_subject)
            await session.flush()
            other_subject_id = other_subject.id
    response = await client.post(
        "/api/v1/admin/teacher-assignments",
        headers=auth_headers(admin_world.admin_token),
        json={
            "teacher_user_id": str(teacher_world.teacher_user_id),
            "academic_year_id": str(student_world["a_year_id"]),
            "section_id": str(student_world["a_section_id"]),
            "subject_id": str(other_subject_id),
            "assignment_role": "subject_teacher",
        },
    )
    assert response.status_code == 404


async def test_assignment_rejects_other_tenant_section(client, admin_world, teacher_world, student_world) -> None:
    response = await client.post(
        "/api/v1/admin/teacher-assignments",
        headers=auth_headers(admin_world.admin_token),
        json={
            "teacher_user_id": str(teacher_world.teacher_user_id),
            "academic_year_id": str(student_world["a_year_id"]),
            "section_id": str(student_world["b_section_id"]),
            "assignment_role": "class_teacher",
        },
    )
    assert response.status_code == 404


async def test_assignment_rejects_teacher_without_local_staff_profile(
    client, admin_world, student_world, db_factory
) -> None:
    from schoolpass.auth.passwords import hash_password
    from schoolpass.identity.models import User

    async with db_factory() as session:
        async with session.begin():
            await apply_tenant_context(
                session,
                TenantContext(actor_type="user", tenant_id=student_world["tenant_b"], user_id=student_world["admin_b"]),
            )
            teacher_b = User(
                id=uuid4(),
                email=f"teacher-b-{uuid4().hex[:6]}@example.invalid",
                password_hash=hash_password("x"),
            )
            session.add(teacher_b)
            await session.flush()
            session.add(
                StaffProfile(
                    tenant_id=student_world["tenant_b"],
                    user_id=teacher_b.id,
                    staff_type="teacher",
                    employee_code="TB-1",
                )
            )
            await session.flush()
            teacher_b_id = teacher_b.id

    response = await client.post(
        "/api/v1/admin/teacher-assignments",
        headers=auth_headers(admin_world.admin_token),
        json={
            "teacher_user_id": str(teacher_b_id),
            "academic_year_id": str(student_world["a_year_id"]),
            "section_id": str(student_world["a_section_id"]),
            "assignment_role": "class_teacher",
        },
    )
    assert response.status_code == 422


async def test_valid_teacher_assignment(client, admin_world, teacher_world, student_world) -> None:
    response = await client.post(
        "/api/v1/admin/teacher-assignments",
        headers=auth_headers(admin_world.admin_token),
        json={
            "teacher_user_id": str(teacher_world.other_teacher_user_id),
            "academic_year_id": str(student_world["a_year_id"]),
            "section_id": str(student_world["a_section_id"]),
            "subject_id": str(teacher_world.subject_id),
            "assignment_role": "subject_teacher",
        },
    )
    assert response.status_code == 200


async def test_non_teacher_staff_rejected(client, admin_world, student_world, db_factory) -> None:
    from schoolpass.auth.passwords import hash_password
    from schoolpass.identity.models import User

    async with db_factory() as session:
        async with session.begin():
            await apply_tenant_context(
                session,
                TenantContext(actor_type="user", tenant_id=admin_world.tenant_id, user_id=admin_world.admin_user_id),
            )
            attendant_user = User(
                id=uuid4(),
                email=f"attendant-{uuid4().hex[:6]}@example.invalid",
                password_hash=hash_password("x"),
            )
            session.add(attendant_user)
            await session.flush()
            session.add(
                StaffProfile(
                    tenant_id=admin_world.tenant_id,
                    user_id=attendant_user.id,
                    staff_type="bus_attendant",
                    employee_code="BA-1",
                )
            )
            await session.flush()
            attendant_id = attendant_user.id
    response = await client.post(
        "/api/v1/admin/teacher-assignments",
        headers=auth_headers(admin_world.admin_token),
        json={
            "teacher_user_id": str(attendant_id),
            "academic_year_id": str(student_world["a_year_id"]),
            "section_id": str(student_world["a_section_id"]),
            "assignment_role": "class_teacher",
        },
    )
    assert response.status_code == 422


async def test_teacher_api_still_works_after_admin_changes(client, teacher_world, admin_world, student_world) -> None:
    await client.patch(
        f"/api/v1/admin/sections/{student_world['a_section_id']}",
        headers=auth_headers(admin_world.admin_token),
        json={"status": "inactive"},
    )
    classes = await client.get("/api/v1/teacher/classes", headers=auth_headers(teacher_world.teacher_token))
    assert classes.status_code == 200
    assert len(classes.json()["items"]) >= 1
    students = await client.get(
        f"/api/v1/teacher/classes/{teacher_world.section_id}/students",
        headers=auth_headers(teacher_world.teacher_token),
    )
    assert students.status_code == 200


async def test_audit_on_academic_create(client, admin_world, db_factory) -> None:
    await client.post(
        "/api/v1/admin/classes",
        headers=auth_headers(admin_world.admin_token),
        json={"code": "AUD", "name": "Audit Class"},
    )
    async with db_factory() as session:
        async with session.begin():
            await apply_tenant_context(
                session,
                TenantContext(actor_type="user", tenant_id=admin_world.tenant_id, user_id=admin_world.admin_user_id),
            )
            count = await session.scalar(
                select(func.count())
                .select_from(AuditLog)
                .where(
                    AuditLog.tenant_id == admin_world.tenant_id,
                    AuditLog.action == "school_class.created",
                )
            )
    assert count and count >= 1
