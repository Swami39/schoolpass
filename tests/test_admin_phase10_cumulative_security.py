"""Cumulative Phase 10 security gaps — imports RBAC and apply guards."""

from __future__ import annotations

from uuid import uuid4

import pytest
from sqlalchemy import select

from admin_helpers import AdminWorld, build_admin_world
from fixtures_students import auth_headers
from schoolpass.auth.passwords import hash_password
from schoolpass.auth.tokens import encode_access_token
from schoolpass.db.session import apply_tenant_context
from schoolpass.identity.models import Role, TenantMembership, User
from schoolpass.tenancy.context import TenantContext


@pytest.fixture
async def admin_world(db_factory, world, settings) -> AdminWorld:
    return await build_admin_world(db_factory, settings=settings, base_world=world)


def _csv_file(content: str) -> tuple[str, bytes, str]:
    return ("file", content.encode(), "text/csv")


async def test_platform_support_has_operations_read_not_imports(client, admin_world, db_factory, settings) -> None:
    async with db_factory() as session:
        async with session.begin():
            await apply_tenant_context(
                session,
                TenantContext(actor_type="system", tenant_id=None, user_id=None),
            )
            support_role = (await session.execute(select(Role).where(Role.name == "platform_support"))).scalar_one()
            user = User(
                id=uuid4(),
                email=f"support-{uuid4().hex[:6]}@example.invalid",
                password_hash=hash_password("x"),
            )
            session.add(user)
            await session.flush()
            await apply_tenant_context(
                session,
                TenantContext(actor_type="user", tenant_id=admin_world.tenant_id, user_id=user.id),
            )
            session.add(
                TenantMembership(tenant_id=admin_world.tenant_id, user_id=user.id, role_id=support_role.id)
            )
            user_id = user.id
    token = encode_access_token(
        settings,
        user_id=user_id,
        tenant_id=admin_world.tenant_id,
        roles=["platform_support"],
        mfa=False,
        platform=False,
    )
    headers = auth_headers(token)
    assert (await client.get("/api/v1/admin/cards", headers=headers)).status_code == 200
    assert (await client.get("/api/v1/admin/imports/types/students/template", headers=headers)).status_code == 403


async def test_finance_denied_imports(client, admin_world, db_factory, settings) -> None:
    async with db_factory() as session:
        async with session.begin():
            await apply_tenant_context(
                session,
                TenantContext(actor_type="user", tenant_id=admin_world.tenant_id, user_id=admin_world.admin_user_id),
            )
            finance_role = (await session.execute(select(Role).where(Role.name == "school_finance"))).scalar_one()
            user = User(
                id=uuid4(),
                email=f"finance-imp-{uuid4().hex[:6]}@example.invalid",
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
    headers = auth_headers(token)
    assert (
        await client.post(
            "/api/v1/admin/imports/students/validate",
            headers=headers,
            files={"file": _csv_file("admission_no,first_name,last_name\nX,Y,Z\n")},
        )
    ).status_code == 403


async def test_import_apply_requires_confirm(client, admin_world) -> None:
    headers = auth_headers(admin_world.admin_token)
    csv_body = "admission_no,first_name,last_name\nIMP-CNF-1,A,B\n"
    validated = await client.post(
        "/api/v1/admin/imports/students/validate",
        headers=headers,
        files={"file": _csv_file(csv_body)},
    )
    digest = validated.json()["content_digest"]
    denied = await client.post(
        "/api/v1/admin/imports/students/apply",
        headers=headers,
        data={"confirm": "false", "content_digest": digest},
        files={"file": _csv_file(csv_body)},
    )
    assert denied.status_code in {400, 422}


async def test_import_apply_rejects_digest_mismatch(client, admin_world) -> None:
    headers = auth_headers(admin_world.admin_token)
    csv_body = "admission_no,first_name,last_name\nIMP-DIG-1,A,B\n"
    await client.post(
        "/api/v1/admin/imports/students/validate",
        headers=headers,
        files={"file": _csv_file(csv_body)},
    )
    bad_digest = "0" * 64
    denied = await client.post(
        "/api/v1/admin/imports/students/apply",
        headers=headers,
        data={"confirm": "true", "content_digest": bad_digest},
        files={"file": _csv_file(csv_body)},
    )
    assert denied.status_code in {400, 422}
