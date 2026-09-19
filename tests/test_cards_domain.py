from __future__ import annotations

import asyncio
from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from fixtures_students import auth_headers
from schoolpass.cards.models import CardAssignment
from schoolpass.cards.services import activate_assignment, create_assignment, register_card
from schoolpass.config import Settings
from schoolpass.db.mixins import utcnow
from schoolpass.db.session import apply_tenant_context, create_engine, session_factory
from schoolpass.tenancy.context import TenantContext


async def test_register_and_search_card(client: AsyncClient, student_world: dict) -> None:
    headers = auth_headers(student_world["token_a"])
    created = await client.post(
        "/api/v1/cards",
        json={"hf_uid": " 04abc123  ", "uhf_epc": "epc-demo-1", "profile": "uid_only"},
        headers=headers,
    )
    assert created.status_code == 200
    body = created.json()
    assert body["hf_uid"] == "04abc123"
    assert body["uhf_epc"] == "EPC-DEMO-1"
    assert body["status"] == "inventory"

    found = await client.get("/api/v1/cards", params={"hf_uid": "04abc123"}, headers=headers)
    assert found.status_code == 200
    assert len(found.json()["items"]) >= 1


async def test_assignment_activate_and_history(client: AsyncClient, student_world: dict) -> None:
    headers = auth_headers(student_world["token_a"])
    card = await client.post(
        "/api/v1/cards",
        json={"hf_uid": f"hf-{uuid4().hex[:8]}", "profile": "uid_only"},
        headers=headers,
    )
    card_id = card.json()["id"]
    assignment = await client.post(
        "/api/v1/card-assignments",
        json={"student_id": str(student_world["a_student_id"]), "physical_card_id": card_id},
        headers=headers,
    )
    assert assignment.status_code == 200
    assignment_id = assignment.json()["id"]
    activated = await client.post(f"/api/v1/card-assignments/{assignment_id}/activate", headers=headers)
    assert activated.status_code == 200
    assert activated.json()["status"] == "active"
    history = await client.get(
        f"/api/v1/students/{student_world['a_student_id']}/cards",
        headers=headers,
    )
    assert len(history.json()["items"]) >= 1


async def test_replace_preserves_history(client: AsyncClient, student_world: dict) -> None:
    headers = auth_headers(student_world["token_a"])
    card1 = (
        await client.post(
            "/api/v1/cards",
            json={"hf_uid": f"hf-{uuid4().hex[:8]}", "profile": "uid_only"},
            headers=headers,
        )
    ).json()
    assign1 = (
        await client.post(
            "/api/v1/card-assignments",
            json={"student_id": str(student_world["a_student_id"]), "physical_card_id": card1["id"]},
            headers=headers,
        )
    ).json()
    await client.post(f"/api/v1/card-assignments/{assign1['id']}/activate", headers=headers)
    card2 = (
        await client.post(
            "/api/v1/cards",
            json={"hf_uid": f"hf-{uuid4().hex[:8]}", "profile": "uid_only"},
            headers=headers,
        )
    ).json()
    replaced = await client.post(
        f"/api/v1/card-assignments/{assign1['id']}/replace",
        json={"physical_card_id": card2["id"], "activate": True},
        headers=headers,
    )
    assert replaced.status_code == 200
    history = await client.get(
        f"/api/v1/students/{student_world['a_student_id']}/cards",
        headers=headers,
    )
    statuses = {item["status"] for item in history.json()["items"]}
    assert "replaced" in statuses
    assert "active" in statuses
    old = (await client.get(f"/api/v1/card-assignments/{assign1['id']}", headers=headers)).json()
    assert old["status"] == "replaced"
    assert old["replaced_by_assignment_id"] == replaced.json()["id"]


async def test_cross_tenant_assignment_fails(db_factory, student_world) -> None:
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
                CardAssignment(
                    tenant_id=student_world["tenant_a"],
                    student_id=student_world["a_student_id"],
                    physical_card_id=student_world["b_card_id"],
                    status="pending",
                    issued_at=utcnow(),
                )
            )
            with pytest.raises(DBAPIError):
                await session.flush()


async def test_rls_force_on_card_tables(engine) -> None:
    async with engine.connect() as conn:
        for table in ("physical_cards", "card_assignments"):
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


async def test_concurrent_active_assignment_conflict(student_world, settings: Settings) -> None:
    engine = create_engine(settings.database_url, null_pool=True)
    factory = session_factory(engine)

    async def run_once(hf_uid: str) -> None:
        async with factory() as session:
            async with session.begin():
                ctx = TenantContext(
                    actor_type="user",
                    tenant_id=student_world["tenant_a"],
                    user_id=student_world["admin_a"],
                )
                await apply_tenant_context(session, ctx)
                card = await register_card(
                    session,
                    ctx,
                    hf_uid=hf_uid,
                    uhf_epc=None,
                    uhf_tid=None,
                    profile="uid_only",
                    manufactured_at=None,
                    request_id="test",
                )
                assignment = await create_assignment(
                    session,
                    ctx,
                    student_id=student_world["a_student_id"],
                    physical_card_id=card.id,
                    request_id="test",
                )
                await activate_assignment(session, ctx, assignment.id, request_id="test")

    results = await asyncio.gather(
        run_once(f"hf-{uuid4().hex[:8]}"),
        run_once(f"hf-{uuid4().hex[:8]}"),
        return_exceptions=True,
    )
    await engine.dispose()
    assert sum(1 for r in results if not isinstance(r, Exception)) == 1
    assert sum(1 for r in results if isinstance(r, Exception)) == 1
