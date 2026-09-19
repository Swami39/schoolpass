"""Admin operations (cards, RFID, transport) — Phase 10C."""

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


async def test_admin_cards_list_and_create(client, admin_world) -> None:
    headers = auth_headers(admin_world.admin_token)
    created = await client.post(
        "/api/v1/admin/cards",
        headers=headers,
        json={"hf_uid": f"ADM-{uuid4().hex[:8]}", "profile": "uid_only"},
    )
    assert created.status_code == 200
    listed = await client.get("/api/v1/admin/cards", headers=headers)
    assert listed.status_code == 200
    assert any(item["id"] == created.json()["id"] for item in listed.json()["items"])


async def test_card_assignment_replace_preserves_history(client, admin_world, student_world) -> None:
    headers = auth_headers(admin_world.admin_token)
    card1 = (
        await client.post(
            "/api/v1/admin/cards",
            headers=headers,
            json={"hf_uid": f"C1-{uuid4().hex[:6]}", "profile": "uid_only"},
        )
    ).json()
    assign = (
        await client.post(
            "/api/v1/admin/card-assignments",
            headers=headers,
            json={"student_id": str(student_world["a_student_id"]), "physical_card_id": card1["id"]},
        )
    ).json()
    await client.post(f"/api/v1/admin/card-assignments/{assign['id']}/activate", headers=headers)
    card2 = (
        await client.post(
            "/api/v1/admin/cards",
            headers=headers,
            json={"hf_uid": f"C2-{uuid4().hex[:6]}", "profile": "uid_only"},
        )
    ).json()
    replaced = await client.post(
        f"/api/v1/admin/card-assignments/{assign['id']}/replace",
        headers=headers,
        json={"physical_card_id": card2["id"]},
    )
    assert replaced.status_code == 200
    history = await client.get(
        f"/api/v1/admin/students/{student_world['a_student_id']}/card-assignments",
        headers=headers,
    )
    assert len(history.json()["items"]) >= 2


async def test_cross_tenant_card_get(client, admin_world, student_world) -> None:
    response = await client.get(
        f"/api/v1/admin/cards/{student_world['b_card_id']}",
        headers=auth_headers(admin_world.admin_token),
    )
    assert response.status_code == 404


async def test_teacher_denied_admin_operations(client, admin_world) -> None:
    assert (
        await client.get("/api/v1/admin/cards", headers=auth_headers(admin_world.teacher_token))
    ).status_code == 403


async def test_rfid_device_list_no_secrets(client, admin_world) -> None:
    response = await client.get("/api/v1/admin/rfid-devices", headers=auth_headers(admin_world.admin_token))
    assert response.status_code == 200
    body = response.json()
    assert "signing_secret" not in str(body).lower()
    assert "secret_encrypted" not in str(body).lower()


async def test_admin_bus_create_and_list(client, admin_world) -> None:
    headers = auth_headers(admin_world.admin_token)
    created = await client.post(
        "/api/v1/admin/buses",
        headers=headers,
        json={"registration_number": f"KA-{uuid4().hex[:6]}", "display_name": "Bus 1", "capacity": 40},
    )
    assert created.status_code == 200
    listed = await client.get("/api/v1/admin/buses", headers=headers)
    assert listed.status_code == 200


async def test_finance_denied_operations(client, admin_world, db_factory, settings) -> None:
    async with db_factory() as session:
        async with session.begin():
            await apply_tenant_context(
                session,
                TenantContext(actor_type="user", tenant_id=admin_world.tenant_id, user_id=admin_world.admin_user_id),
            )
            role = (await session.execute(select(Role).where(Role.name == "school_finance"))).scalar_one()
            user = User(
                id=uuid4(),
                email=f"fin-{uuid4().hex[:6]}@example.invalid",
                password_hash=hash_password("x"),
            )
            session.add(user)
            await session.flush()
            session.add(TenantMembership(tenant_id=admin_world.tenant_id, user_id=user.id, role_id=role.id))
            uid = user.id
    token = encode_access_token(
        settings, user_id=uid, tenant_id=admin_world.tenant_id, roles=["school_finance"], mfa=False, platform=False
    )
    assert (await client.get("/api/v1/admin/buses", headers=auth_headers(token))).status_code == 403


async def test_tenant_id_in_card_body_rejected(client, admin_world) -> None:
    response = await client.post(
        "/api/v1/admin/cards",
        headers=auth_headers(admin_world.admin_token),
        json={"hf_uid": f"X-{uuid4().hex[:6]}", "profile": "uid_only", "tenant_id": str(admin_world.tenant_id)},
    )
    assert response.status_code == 422
