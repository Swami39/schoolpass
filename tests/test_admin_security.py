"""Security and behavior tests for school admin APIs (Phase 10.1)."""

from __future__ import annotations

import pytest
from sqlalchemy import func, select

from admin_helpers import AdminWorld, build_admin_world
from fixtures_students import auth_headers
from schoolpass.auth.tokens import encode_access_token
from schoolpass.db.session import apply_tenant_context
from schoolpass.identity.models import AuditLog, Tenant, TenantMembership
from schoolpass.people.models import FileMetadata
from schoolpass.tenancy.context import TenantContext


@pytest.fixture
async def admin_world(db_factory, world, settings) -> AdminWorld:
    return await build_admin_world(db_factory, settings=settings, base_world=world)


async def test_school_admin_can_read_own_school(client, admin_world) -> None:
    response = await client.get("/api/v1/admin/school", headers=auth_headers(admin_world.admin_token))
    assert response.status_code == 200
    body = response.json()
    assert body["id"] == str(admin_world.tenant_id)
    assert body["legal_name"] == "North Test School"


async def test_school_admin_can_update_own_school(client, admin_world) -> None:
    response = await client.patch(
        "/api/v1/admin/school",
        headers=auth_headers(admin_world.admin_token),
        json={
            "display_name": "North Campus",
            "contact_email": "office@north.example.invalid",
            "city": "Chennai",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["display_name"] == "North Campus"
    assert body["contact_email"] == "office@north.example.invalid"
    assert body["city"] == "Chennai"


async def test_unauthenticated_rejected(client) -> None:
    response = await client.get("/api/v1/admin/school")
    assert response.status_code == 401


async def test_inactive_membership_rejected(client, db_factory, admin_world, settings) -> None:
    async with db_factory() as session:
        async with session.begin():
            await apply_tenant_context(
                session,
                TenantContext(actor_type="user", tenant_id=admin_world.tenant_id, user_id=admin_world.admin_user_id),
            )
            result = await session.execute(
                select(TenantMembership).where(
                    TenantMembership.user_id == admin_world.admin_user_id,
                    TenantMembership.tenant_id == admin_world.tenant_id,
                )
            )
            membership = result.scalar_one()
            membership.status = "suspended"

    token = encode_access_token(
        settings,
        user_id=admin_world.admin_user_id,
        tenant_id=admin_world.tenant_id,
        roles=["school_admin"],
        mfa=False,
        platform=False,
    )
    response = await client.get("/api/v1/admin/school", headers=auth_headers(token))
    assert response.status_code == 403


async def test_non_admin_cannot_update_school(client, admin_world) -> None:
    response = await client.patch(
        "/api/v1/admin/school",
        headers=auth_headers(admin_world.teacher_token),
        json={"display_name": "Hijack"},
    )
    assert response.status_code == 403


async def test_tenant_a_admin_cannot_read_with_tenant_b_context(client, admin_world, settings) -> None:
    token = encode_access_token(
        settings,
        user_id=admin_world.admin_user_id,
        tenant_id=admin_world.other_tenant_id,
        roles=["school_admin"],
        mfa=False,
        platform=False,
    )
    response = await client.get("/api/v1/admin/school", headers=auth_headers(token))
    assert response.status_code == 403


async def test_tenant_a_admin_cannot_update_tenant_b_via_context(client, admin_world, settings, db_factory) -> None:
    token = encode_access_token(
        settings,
        user_id=admin_world.admin_user_id,
        tenant_id=admin_world.other_tenant_id,
        roles=["school_admin"],
        mfa=False,
        platform=False,
    )
    response = await client.patch(
        "/api/v1/admin/school",
        headers=auth_headers(token),
        json={"display_name": "South Hack"},
    )
    assert response.status_code == 403

    async with db_factory() as session:
        async with session.begin():
            await apply_tenant_context(session, TenantContext(actor_type="system", tenant_id=None, user_id=None))
            south = await session.get(Tenant, admin_world.other_tenant_id)
            assert south is not None
            assert south.display_name is None


async def test_client_tenant_id_in_body_does_not_bypass_context(client, admin_world, settings) -> None:
    rejected = await client.patch(
        "/api/v1/admin/school",
        headers=auth_headers(admin_world.admin_token),
        json={
            "display_name": "Legit Update",
            "tenant_id": str(admin_world.other_tenant_id),
        },
    )
    assert rejected.status_code == 422

    response = await client.patch(
        "/api/v1/admin/school",
        headers=auth_headers(admin_world.admin_token),
        json={"display_name": "Legit Update"},
    )
    assert response.status_code == 200
    assert response.json()["id"] == str(admin_world.tenant_id)
    assert response.json()["display_name"] == "Legit Update"

    peek = await client.get("/api/v1/admin/school", headers=auth_headers(admin_world.admin_token))
    assert peek.json()["id"] == str(admin_world.tenant_id)

    token_b = encode_access_token(
        settings,
        user_id=admin_world.admin_user_id,
        tenant_id=admin_world.other_tenant_id,
        roles=["school_admin"],
        mfa=False,
        platform=False,
    )
    # Admin has no membership on B — cannot read B profile even if they tried to poison A's row.
    denied = await client.get("/api/v1/admin/school", headers=auth_headers(token_b))
    assert denied.status_code == 403


async def test_audit_event_on_successful_update(client, admin_world, db_factory) -> None:
    await client.patch(
        "/api/v1/admin/school",
        headers=auth_headers(admin_world.admin_token),
        json={"state": "Tamil Nadu"},
    )
    async with db_factory() as session:
        async with session.begin():
            await apply_tenant_context(
                session,
                TenantContext(
                    actor_type="user",
                    tenant_id=admin_world.tenant_id,
                    user_id=admin_world.admin_user_id,
                ),
            )
            count = await session.scalar(
                select(func.count())
                .select_from(AuditLog)
                .where(
                    AuditLog.action == "tenant.profile.updated",
                    AuditLog.resource_id == admin_world.tenant_id,
                    AuditLog.tenant_id == admin_world.tenant_id,
                )
            )
    assert count and count >= 1


async def test_cannot_set_logo_file_from_other_tenant(
    client, admin_world, db_factory, student_world
) -> None:
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
                purpose="school_logo",
                blob_key=f"{student_world['tenant_b']}/logos/other.png",
                classification="SENSITIVE_CHILD_DATA",
                created_by=student_world["admin_b"],
            )
            session.add(row)
            await session.flush()
            other_file_id = row.id

    response = await client.patch(
        "/api/v1/admin/school",
        headers=auth_headers(admin_world.admin_token),
        json={"logo_file_id": str(other_file_id)},
    )
    assert response.status_code == 422


async def test_unknown_patch_fields_rejected(client, admin_world) -> None:
    response = await client.patch(
        "/api/v1/admin/school",
        headers=auth_headers(admin_world.admin_token),
        json={"slug": "hijacked-slug"},
    )
    assert response.status_code == 422


async def test_teacher_with_tenant_read_cannot_update_school(client, admin_world) -> None:
    read = await client.get("/api/v1/admin/school", headers=auth_headers(admin_world.teacher_token))
    assert read.status_code == 200
    patch = await client.patch(
        "/api/v1/admin/school",
        headers=auth_headers(admin_world.teacher_token),
        json={"display_name": "Nope"},
    )
    assert patch.status_code == 403


async def test_invalid_profile_data_rejected(client, admin_world) -> None:
    response = await client.patch(
        "/api/v1/admin/school",
        headers=auth_headers(admin_world.admin_token),
        json={"legal_name": ""},
    )
    assert response.status_code == 422

    bad_country = await client.patch(
        "/api/v1/admin/school",
        headers=auth_headers(admin_world.admin_token),
        json={"country": "IND"},
    )
    assert bad_country.status_code == 422
