"""RBAC, audit, and response security for admin people APIs."""

from __future__ import annotations

from uuid import uuid4

import pytest
from sqlalchemy import func, select

from admin_helpers import AdminWorld, build_admin_world
from fixtures_students import auth_headers
from schoolpass.auth.passwords import hash_password
from schoolpass.auth.tokens import encode_access_token
from schoolpass.db.session import apply_tenant_context
from schoolpass.identity.models import AuditLog, Role, TenantMembership, User
from schoolpass.tenancy.context import TenantContext


@pytest.fixture
async def admin_world(db_factory, world, settings) -> AdminWorld:
    return await build_admin_world(db_factory, settings=settings, base_world=world)


async def test_school_finance_denied_people_admin(client, admin_world, db_factory, settings) -> None:
    async with db_factory() as session:
        async with session.begin():
            await apply_tenant_context(
                session,
                TenantContext(actor_type="user", tenant_id=admin_world.tenant_id, user_id=admin_world.admin_user_id),
            )
            finance_role = (await session.execute(select(Role).where(Role.name == "school_finance"))).scalar_one()
            user = User(
                id=uuid4(),
                email=f"finance-{uuid4().hex[:6]}@example.invalid",
                password_hash=hash_password("x"),
            )
            session.add(user)
            await session.flush()
            session.add(
                TenantMembership(tenant_id=admin_world.tenant_id, user_id=user.id, role_id=finance_role.id)
            )
            user_id = user.id
    token = encode_access_token(
        settings,
        user_id=user_id,
        tenant_id=admin_world.tenant_id,
        roles=["school_finance"],
        mfa=False,
        platform=False,
    )
    assert (await client.get("/api/v1/admin/students", headers=auth_headers(token))).status_code == 403


async def test_teacher_cannot_write_staff(client, admin_world) -> None:
    response = await client.post(
        "/api/v1/admin/staff",
        headers=auth_headers(admin_world.teacher_token),
        json={"user_id": str(uuid4()), "staff_type": "office"},
    )
    assert response.status_code == 403


async def test_staff_response_excludes_secrets(client, admin_world, db_factory) -> None:
    async with db_factory() as session:
        async with session.begin():
            await apply_tenant_context(
                session,
                TenantContext(actor_type="user", tenant_id=admin_world.tenant_id, user_id=admin_world.admin_user_id),
            )
            user = User(
                id=uuid4(),
                email=f"staff-view-{uuid4().hex[:6]}@example.invalid",
                password_hash=hash_password("super-secret"),
            )
            session.add(user)
            await session.flush()
            user_id = user.id
    created = await client.post(
        "/api/v1/admin/staff",
        headers=auth_headers(admin_world.admin_token),
        json={"user_id": str(user_id), "staff_type": "office", "employee_code": "O-1"},
    )
    assert created.status_code == 200
    body = created.json()
    assert "password_hash" not in body
    assert "refresh" not in str(body).lower()


async def test_staff_update_noop_skips_audit(client, admin_world, db_factory) -> None:
    async with db_factory() as session:
        async with session.begin():
            await apply_tenant_context(
                session,
                TenantContext(actor_type="user", tenant_id=admin_world.tenant_id, user_id=admin_world.admin_user_id),
            )
            user = User(
                id=uuid4(),
                email=f"staff-audit-{uuid4().hex[:6]}@example.invalid",
                password_hash=hash_password("x"),
            )
            session.add(user)
            await session.flush()
            user_id = user.id
    created = await client.post(
        "/api/v1/admin/staff",
        headers=auth_headers(admin_world.admin_token),
        json={"user_id": str(user_id), "staff_type": "finance", "employee_code": "F-1"},
    )
    staff_id = created.json()["id"]
    before = await _audit_count(db_factory, admin_world, "staff.updated")
    patch = await client.patch(
        f"/api/v1/admin/staff/{staff_id}",
        headers=auth_headers(admin_world.admin_token),
        json={"employee_code": "F-1"},
    )
    assert patch.status_code == 200
    after = await _audit_count(db_factory, admin_world, "staff.updated")
    assert after == before


async def test_enrollment_close_audit(client, admin_world, student_world, db_factory) -> None:
    student = await client.post(
        "/api/v1/admin/students",
        headers=auth_headers(admin_world.admin_token),
        json={
            "admission_no": f"CLS-{uuid4().hex[:6]}",
            "first_name": "Close",
            "last_name": "Audit",
        },
    )
    student_id = student.json()["id"]
    created = await client.post(
        "/api/v1/admin/enrollments",
        headers=auth_headers(admin_world.admin_token),
        json={
            "student_id": student_id,
            "academic_year_id": str(student_world["a_year_id"]),
            "class_id": str(student_world["a_class_id"]),
            "section_id": str(student_world["a_section_id"]),
            "starts_on": "2025-04-01",
        },
    )
    enrollment_id = created.json()["id"]
    await client.post(
        f"/api/v1/admin/enrollments/{enrollment_id}/close",
        headers=auth_headers(admin_world.admin_token),
        json={"ends_on": "2025-12-31", "status": "completed"},
    )
    count = await _audit_count(db_factory, admin_world, "enrollment.closed")
    assert count >= 1


async def _audit_count(db_factory, admin_world: AdminWorld, action: str) -> int:
    async with db_factory() as session:
        async with session.begin():
            await apply_tenant_context(
                session,
                TenantContext(actor_type="user", tenant_id=admin_world.tenant_id, user_id=admin_world.admin_user_id),
            )
            value = await session.scalar(
                select(func.count())
                .select_from(AuditLog)
                .where(AuditLog.tenant_id == admin_world.tenant_id, AuditLog.action == action)
            )
    return int(value or 0)
