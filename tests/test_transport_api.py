from __future__ import annotations

from uuid import uuid4

from httpx import AsyncClient
from sqlalchemy import select

from fixtures_students import auth_headers
from schoolpass.auth.passwords import hash_password
from schoolpass.auth.tokens import encode_access_token
from schoolpass.config import Settings
from schoolpass.db.session import apply_tenant_context
from schoolpass.identity.models import Role, StaffProfile, TenantMembership, User
from schoolpass.tenancy.context import TenantContext


async def _role_token(
    db_factory,
    student_world: dict,
    settings: Settings,
    role_name: str,
) -> str:
    password = hash_password("role-test-password")
    async with db_factory() as session:
        async with session.begin():
            await apply_tenant_context(
                session,
                TenantContext(actor_type="system", tenant_id=None, user_id=None),
            )
            role = (await session.execute(select(Role).where(Role.name == role_name))).scalar_one()
            user = User(
                id=uuid4(),
                email=f"{role_name}-{uuid4().hex[:6]}@example.invalid",
                password_hash=password,
            )
            session.add(user)
            await session.flush()
            await apply_tenant_context(
                session,
                TenantContext(actor_type="user", tenant_id=student_world["tenant_a"], user_id=user.id),
            )
            session.add(
                TenantMembership(
                    tenant_id=student_world["tenant_a"],
                    user_id=user.id,
                    role_id=role.id,
                )
            )
            if role_name == "bus_attendant":
                session.add(
                    StaffProfile(
                        tenant_id=student_world["tenant_a"],
                        user_id=user.id,
                        staff_type="attendant",
                        employee_code=f"ST-{uuid4().hex[:4]}",
                    )
                )
            await session.flush()
            user_id = user.id
    return encode_access_token(
        settings,
        user_id=user_id,
        tenant_id=student_world["tenant_a"],
        roles=[role_name],
        mfa=False,
        platform=False,
    )


async def _full_stack(client: AsyncClient, student_world: dict, db_factory, settings: Settings) -> dict:
    headers = auth_headers(student_world["token_a"])
    bus = (
        await client.post(
            "/api/v1/buses",
            json={
                "registration_number": f"KA-{uuid4().hex[:6]}",
                "display_name": "Trip Bus",
                "capacity": 40,
            },
            headers=headers,
        )
    ).json()
    route = (
        await client.post(
            "/api/v1/routes",
            json={"name": "Trip Route", "code": f"TR-{uuid4().hex[:4]}", "direction": "pickup"},
            headers=headers,
        )
    ).json()
    stop = (
        await client.post(
            f"/api/v1/routes/{route['id']}/stops",
            json={
                "name": "Main Stop",
                "sequence": 1,
                "latitude": "12.971600",
                "longitude": "77.594600",
            },
            headers=headers,
        )
    ).json()
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
            existing = (
                await session.execute(
                    select(StaffProfile).where(
                        StaffProfile.tenant_id == student_world["tenant_a"],
                        StaffProfile.user_id == student_world["admin_a"],
                    )
                )
            ).scalar_one_or_none()
            if existing is None:
                session.add(
                    StaffProfile(
                        tenant_id=student_world["tenant_a"],
                        user_id=student_world["admin_a"],
                        staff_type="admin",
                        employee_code=f"ADM-{uuid4().hex[:4]}",
                    )
                )
                await session.flush()
    attendant = (
        await client.post(
            "/api/v1/transport-attendants",
            json={"user_id": str(student_world["admin_a"]), "employee_code": f"ATT-{uuid4().hex[:4]}"},
            headers=headers,
        )
    ).json()
    return {
        "headers": headers,
        "bus": bus,
        "route": route,
        "stop": stop,
        "attendant": attendant,
        "service_date": "2026-09-22",
    }


async def test_bus_crud_and_retire(client: AsyncClient, student_world: dict) -> None:
    headers = auth_headers(student_world["token_a"])
    created = await client.post(
        "/api/v1/buses",
        json={
            "registration_number": f"KA-{uuid4().hex[:6]}",
            "display_name": "School Bus",
            "capacity": 42,
        },
        headers=headers,
    )
    assert created.status_code == 200
    bus_id = created.json()["id"]
    fetched = await client.get(f"/api/v1/buses/{bus_id}", headers=headers)
    assert fetched.status_code == 200
    patched = await client.patch(
        f"/api/v1/buses/{bus_id}",
        json={"display_name": "Updated Bus"},
        headers=headers,
    )
    assert patched.status_code == 200
    retired = await client.post(f"/api/v1/buses/{bus_id}/retire", headers=headers)
    assert retired.status_code == 200
    assert retired.json()["status"] == "retired"


async def test_bus_tenant_isolation(client: AsyncClient, student_world: dict) -> None:
    headers_a = auth_headers(student_world["token_a"])
    bus = (
        await client.post(
            "/api/v1/buses",
            json={
                "registration_number": f"KA-{uuid4().hex[:6]}",
                "display_name": "Tenant A Bus",
                "capacity": 30,
            },
            headers=headers_a,
        )
    ).json()
    headers_b = auth_headers(student_world["token_b"])
    cross = await client.get(f"/api/v1/buses/{bus['id']}", headers=headers_b)
    assert cross.status_code == 404


async def test_bus_attendant_cannot_create_bus(
    client: AsyncClient,
    db_factory,
    student_world: dict,
    settings: Settings,
) -> None:
    token = await _role_token(db_factory, student_world, settings, "bus_attendant")
    response = await client.post(
        "/api/v1/buses",
        json={
            "registration_number": f"KA-{uuid4().hex[:6]}",
            "display_name": "Forbidden",
            "capacity": 30,
        },
        headers=auth_headers(token),
    )
    assert response.status_code == 403


async def test_parent_cannot_create_bus(
    client: AsyncClient,
    db_factory,
    student_world: dict,
    settings: Settings,
) -> None:
    token = await _role_token(db_factory, student_world, settings, "parent")
    response = await client.post(
        "/api/v1/buses",
        json={
            "registration_number": f"KA-{uuid4().hex[:6]}",
            "display_name": "Parent Bus",
            "capacity": 30,
        },
        headers=auth_headers(token),
    )
    assert response.status_code == 403


async def test_route_lifecycle_api(client: AsyncClient, student_world: dict) -> None:
    headers = auth_headers(student_world["token_a"])
    route = (
        await client.post(
            "/api/v1/routes",
            json={"name": "North", "code": f"N-{uuid4().hex[:4]}", "direction": "pickup"},
            headers=headers,
        )
    ).json()
    deactivated = await client.post(f"/api/v1/routes/{route['id']}/deactivate", headers=headers)
    assert deactivated.status_code == 200
    activated = await client.post(f"/api/v1/routes/{route['id']}/activate", headers=headers)
    assert activated.status_code == 200
    retired = await client.post(f"/api/v1/routes/{route['id']}/retire", headers=headers)
    assert retired.status_code == 200


async def test_route_stops_reorder(client: AsyncClient, student_world: dict) -> None:
    headers = auth_headers(student_world["token_a"])
    route = (
        await client.post(
            "/api/v1/routes",
            json={"name": "Reorder Route", "code": f"RR-{uuid4().hex[:4]}", "direction": "pickup"},
            headers=headers,
        )
    ).json()
    stop1 = (
        await client.post(
            f"/api/v1/routes/{route['id']}/stops",
            json={"name": "S1", "sequence": 1, "latitude": "12.97", "longitude": "77.59"},
            headers=headers,
        )
    ).json()
    stop2 = (
        await client.post(
            f"/api/v1/routes/{route['id']}/stops",
            json={"name": "S2", "sequence": 2, "latitude": "12.98", "longitude": "77.60"},
            headers=headers,
        )
    ).json()
    reordered = await client.post(
        f"/api/v1/routes/{route['id']}/stops/reorder",
        json={"stop_ids": [stop2["id"], stop1["id"]]},
        headers=headers,
    )
    assert reordered.status_code == 200
    sequences = [item["sequence"] for item in reordered.json()["items"]]
    assert sequences == [1, 2]


async def test_transport_assignment_flow(
    client: AsyncClient,
    student_world: dict,
    db_factory,
    settings: Settings,
) -> None:
    stack = await _full_stack(client, student_world, db_factory, settings)
    headers = stack["headers"]
    created = await client.post(
        "/api/v1/transport-assignments",
        json={
            "student_id": str(student_world["a_student_id"]),
            "route_id": stack["route"]["id"],
            "stop_id": stack["stop"]["id"],
            "effective_from": "2026-01-01",
        },
        headers=headers,
    )
    assert created.status_code == 200
    assignment_id = created.json()["id"]
    suspended = await client.post(f"/api/v1/transport-assignments/{assignment_id}/suspend", headers=headers)
    assert suspended.status_code == 200
    cancelled = await client.post(f"/api/v1/transport-assignments/{assignment_id}/cancel", headers=headers)
    assert cancelled.status_code == 200


async def test_trip_lifecycle_api(client: AsyncClient, student_world: dict, db_factory, settings: Settings) -> None:
    stack = await _full_stack(client, student_world, db_factory, settings)
    headers = stack["headers"]
    trip = (
        await client.post(
            "/api/v1/trips",
            json={
                "bus_id": stack["bus"]["id"],
                "route_id": stack["route"]["id"],
                "attendant_id": stack["attendant"]["id"],
                "service_date": stack["service_date"],
                "shift": "pickup",
            },
            headers=headers,
        )
    ).json()
    assert trip["status"] == "scheduled"
    started = await client.post(f"/api/v1/trips/{trip['id']}/start", headers=headers)
    assert started.status_code == 200
    assert started.json()["status"] == "boarding"
    begun = await client.post(f"/api/v1/trips/{trip['id']}/begin", headers=headers)
    assert begun.status_code == 200
    assert begun.json()["status"] == "in_progress"
    completed = await client.post(f"/api/v1/trips/{trip['id']}/complete", headers=headers)
    assert completed.status_code == 200
    assert completed.json()["status"] == "completed"


async def test_trip_invalid_transition(
    client: AsyncClient,
    student_world: dict,
    db_factory,
    settings: Settings,
) -> None:
    stack = await _full_stack(client, student_world, db_factory, settings)
    headers = stack["headers"]
    trip = (
        await client.post(
            "/api/v1/trips",
            json={
                "bus_id": stack["bus"]["id"],
                "route_id": stack["route"]["id"],
                "attendant_id": stack["attendant"]["id"],
                "service_date": stack["service_date"],
                "shift": "pickup",
            },
            headers=headers,
        )
    ).json()
    complete = await client.post(f"/api/v1/trips/{trip['id']}/complete", headers=headers)
    assert complete.status_code == 422


async def test_retired_bus_rejected_for_trip(
    client: AsyncClient,
    student_world: dict,
    db_factory,
    settings: Settings,
) -> None:
    stack = await _full_stack(client, student_world, db_factory, settings)
    headers = stack["headers"]
    await client.post(f"/api/v1/buses/{stack['bus']['id']}/retire", headers=headers)
    response = await client.post(
        "/api/v1/trips",
        json={
            "bus_id": stack["bus"]["id"],
            "route_id": stack["route"]["id"],
            "attendant_id": stack["attendant"]["id"],
            "service_date": stack["service_date"],
            "shift": "pickup",
        },
        headers=headers,
    )
    assert response.status_code == 422


async def test_unauthenticated_returns_401(client: AsyncClient) -> None:
    response = await client.get("/api/v1/buses")
    assert response.status_code == 401
