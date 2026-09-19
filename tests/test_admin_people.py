"""Admin people administration API tests (Phase 10B)."""

from __future__ import annotations

from datetime import date
from uuid import uuid4

import pytest
from sqlalchemy import func, select

from admin_helpers import AdminWorld, build_admin_world
from fixtures_students import auth_headers
from schoolpass.auth.passwords import hash_password
from schoolpass.auth.tokens import encode_access_token
from schoolpass.db.session import apply_tenant_context
from schoolpass.identity.models import AuditLog, Role, TenantMembership, User
from schoolpass.people.models import FileMetadata, Student
from schoolpass.tenancy.context import TenantContext


@pytest.fixture
async def admin_world(db_factory, world, settings) -> AdminWorld:
    return await build_admin_world(db_factory, settings=settings, base_world=world)


async def test_admin_lists_people(client, admin_world, student_world) -> None:
    students = await client.get("/api/v1/admin/students", headers=auth_headers(admin_world.admin_token))
    assert students.status_code == 200
    assert any(s["id"] == str(student_world["a_student_id"]) for s in students.json()["items"])
    guardians = await client.get("/api/v1/admin/guardians", headers=auth_headers(admin_world.admin_token))
    assert guardians.status_code == 200
    staff = await client.get("/api/v1/admin/staff", headers=auth_headers(admin_world.admin_token))
    assert staff.status_code == 200


async def test_unauthenticated_rejected(client) -> None:
    assert (await client.get("/api/v1/admin/students")).status_code == 401


async def test_teacher_read_students_write_denied(client, admin_world) -> None:
    read = await client.get("/api/v1/admin/students", headers=auth_headers(admin_world.teacher_token))
    assert read.status_code == 200
    write = await client.post(
        "/api/v1/admin/students",
        headers=auth_headers(admin_world.teacher_token),
        json={"admission_no": "X", "first_name": "N", "last_name": "O"},
    )
    assert write.status_code == 403


async def test_cross_tenant_student_get_not_found(client, admin_world, student_world) -> None:
    response = await client.get(
        f"/api/v1/admin/students/{student_world['b_student_id']}",
        headers=auth_headers(admin_world.admin_token),
    )
    assert response.status_code == 404


async def test_tenant_id_in_student_body_rejected(client, admin_world) -> None:
    response = await client.post(
        "/api/v1/admin/students",
        headers=auth_headers(admin_world.admin_token),
        json={
            "admission_no": f"ADM-{uuid4().hex[:6]}",
            "first_name": "A",
            "last_name": "B",
            "tenant_id": str(admin_world.other_tenant_id),
        },
    )
    assert response.status_code == 422


async def test_create_student_and_enrollment(client, admin_world, student_world) -> None:
    created = await client.post(
        "/api/v1/admin/students",
        headers=auth_headers(admin_world.admin_token),
        json={
            "admission_no": f"ADM-{uuid4().hex[:6]}",
            "first_name": "New",
            "last_name": "Student",
        },
    )
    assert created.status_code == 200
    student_id = created.json()["id"]
    enrollment = await client.post(
        "/api/v1/admin/enrollments",
        headers=auth_headers(admin_world.admin_token),
        json={
            "student_id": student_id,
            "academic_year_id": str(student_world["a_year_id"]),
            "class_id": str(student_world["a_class_id"]),
            "section_id": str(student_world["a_section_id"]),
            "starts_on": date.today().isoformat(),
        },
    )
    assert enrollment.status_code == 200


async def test_enrollment_cross_tenant_section_rejected(client, admin_world, student_world) -> None:
    response = await client.post(
        "/api/v1/admin/enrollments",
        headers=auth_headers(admin_world.admin_token),
        json={
            "student_id": str(student_world["a_student_id"]),
            "academic_year_id": str(student_world["a_year_id"]),
            "class_id": str(student_world["b_class_id"]),
            "section_id": str(student_world["b_section_id"]),
            "starts_on": date.today().isoformat(),
        },
    )
    assert response.status_code == 404


async def test_cross_tenant_photo_rejected(client, admin_world, student_world, db_factory) -> None:
    async with db_factory() as session:
        async with session.begin():
            await apply_tenant_context(
                session,
                TenantContext(actor_type="user", tenant_id=student_world["tenant_b"], user_id=student_world["admin_b"]),
            )
            file_row = FileMetadata(
                tenant_id=student_world["tenant_b"],
                purpose="student_photo",
                blob_key=f"{student_world['tenant_b']}/photos/x.jpg",
                classification="SENSITIVE_CHILD_DATA",
                created_by=student_world["admin_b"],
            )
            session.add(file_row)
            await session.flush()
            file_id = file_row.id
    response = await client.patch(
        f"/api/v1/admin/students/{student_world['a_student_id']}",
        headers=auth_headers(admin_world.admin_token),
        json={"photo_file_id": str(file_id)},
    )
    assert response.status_code == 422


async def test_create_staff_for_user(client, admin_world, db_factory) -> None:
    async with db_factory() as session:
        async with session.begin():
            await apply_tenant_context(
                session,
                TenantContext(actor_type="user", tenant_id=admin_world.tenant_id, user_id=admin_world.admin_user_id),
            )
            user = User(
                id=uuid4(),
                email=f"new-teacher-{uuid4().hex[:6]}@example.invalid",
                password_hash=hash_password("x"),
            )
            session.add(user)
            await session.flush()
            user_id = user.id
    response = await client.post(
        "/api/v1/admin/staff",
        headers=auth_headers(admin_world.admin_token),
        json={"user_id": str(user_id), "staff_type": "teacher", "employee_code": "T-NEW"},
    )
    assert response.status_code == 200
    assert response.json()["staff_type"] == "teacher"


async def test_guardian_link_cross_tenant_rejected(client, admin_world, student_world) -> None:
    response = await client.post(
        f"/api/v1/admin/students/{student_world['a_student_id']}/guardians",
        headers=auth_headers(admin_world.admin_token),
        json={
            "guardian_id": str(student_world["b_guardian_id"]),
            "relationship_type": "parent",
        },
    )
    assert response.status_code == 404


async def test_enrollment_update_preserves_student(client, admin_world, student_world, db_factory) -> None:
    list_resp = await client.get(
        f"/api/v1/admin/students/{student_world['a_student_id']}/enrollments",
        headers=auth_headers(admin_world.admin_token),
    )
    if not list_resp.json()["items"]:
        await client.post(
            "/api/v1/admin/enrollments",
            headers=auth_headers(admin_world.admin_token),
            json={
                "student_id": str(student_world["a_student_id"]),
                "academic_year_id": str(student_world["a_year_id"]),
                "class_id": str(student_world["a_class_id"]),
                "section_id": str(student_world["a_section_id"]),
                "starts_on": date.today().isoformat(),
            },
        )
        list_resp = await client.get(
            f"/api/v1/admin/students/{student_world['a_student_id']}/enrollments",
            headers=auth_headers(admin_world.admin_token),
        )
    enrollment_id = list_resp.json()["items"][0]["id"]
    patch = await client.patch(
        f"/api/v1/admin/enrollments/{enrollment_id}",
        headers=auth_headers(admin_world.admin_token),
        json={"status": "active"},
    )
    assert patch.status_code == 200
    async with db_factory() as session:
        async with session.begin():
            await apply_tenant_context(
                session,
                TenantContext(actor_type="user", tenant_id=admin_world.tenant_id, user_id=admin_world.admin_user_id),
            )
            student = await session.get(Student, student_world["a_student_id"])
            assert student is not None


async def test_audit_on_student_create(client, admin_world, db_factory) -> None:
    await client.post(
        "/api/v1/admin/students",
        headers=auth_headers(admin_world.admin_token),
        json={
            "admission_no": f"AUD-{uuid4().hex[:6]}",
            "first_name": "Audit",
            "last_name": "Student",
        },
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
                .where(AuditLog.tenant_id == admin_world.tenant_id, AuditLog.action == "student.created")
            )
    assert count and count >= 1


async def test_parent_denied_admin_people(client, admin_world, db_factory, settings) -> None:
    async with db_factory() as session:
        async with session.begin():
            await apply_tenant_context(
                session,
                TenantContext(actor_type="user", tenant_id=admin_world.tenant_id, user_id=admin_world.admin_user_id),
            )
            parent_role = (
                await session.execute(select(Role).where(Role.name == "parent"))
            ).scalar_one()
            parent_user = User(
                id=uuid4(),
                email=f"parent-{uuid4().hex[:6]}@example.invalid",
                password_hash=hash_password("x"),
            )
            session.add(parent_user)
            await session.flush()
            session.add(
                TenantMembership(
                    tenant_id=admin_world.tenant_id,
                    user_id=parent_user.id,
                    role_id=parent_role.id,
                )
            )
            parent_user_id = parent_user.id
    token = encode_access_token(
        settings,
        user_id=parent_user_id,
        tenant_id=admin_world.tenant_id,
        roles=["parent"],
        mfa=False,
        platform=False,
    )
    assert (await client.get("/api/v1/admin/students", headers=auth_headers(token))).status_code == 403


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
    assert (await client.get("/api/v1/admin/students", headers=auth_headers(token))).status_code == 403
