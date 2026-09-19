from __future__ import annotations

from datetime import date
from uuid import UUID, uuid4

import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import select

from schoolpass.auth.passwords import hash_password
from schoolpass.auth.tokens import encode_access_token
from schoolpass.cards.models import PhysicalCard
from schoolpass.config import Settings
from schoolpass.db.session import apply_tenant_context
from schoolpass.identity.models import Role, TenantMembership, User
from schoolpass.people.models import AcademicYear, Guardian, SchoolClass, Section, Student
from schoolpass.tenancy.context import TenantContext


@pytest_asyncio.fixture
async def student_world(db_factory, world: dict[str, UUID], settings: Settings) -> dict[str, UUID]:
    """Synthetic child/guardian fixtures — clearly fake data."""
    password = hash_password("correct-horse-battery")
    async with db_factory() as session:
        async with session.begin():
            await apply_tenant_context(session, TenantContext(actor_type="system", tenant_id=None, user_id=None))
            roles = {
                row.name: row for row in (await session.execute(select(Role).where(Role.is_system.is_(True)))).scalars()
            }
            admin_a = User(
                id=uuid4(),
                email=f"admin-a-{uuid4().hex[:6]}@example.invalid",
                password_hash=password,
            )
            admin_b = User(
                id=uuid4(),
                email=f"admin-b-{uuid4().hex[:6]}@example.invalid",
                password_hash=password,
            )
            session.add_all([admin_a, admin_b])
            await session.flush()
            await apply_tenant_context(
                session,
                TenantContext(actor_type="user", tenant_id=world["tenant_a"], user_id=admin_a.id),
            )
            session.add(
                TenantMembership(
                    tenant_id=world["tenant_a"],
                    user_id=admin_a.id,
                    role_id=roles["school_admin"].id,
                )
            )
            await session.flush()
            await apply_tenant_context(
                session,
                TenantContext(actor_type="user", tenant_id=world["tenant_b"], user_id=admin_b.id),
            )
            session.add(
                TenantMembership(
                    tenant_id=world["tenant_b"],
                    user_id=admin_b.id,
                    role_id=roles["school_admin"].id,
                )
            )
            await session.flush()

            async def seed_tenant(tenant_id: UUID, actor_id: UUID) -> dict[str, UUID]:
                await apply_tenant_context(
                    session,
                    TenantContext(actor_type="user", tenant_id=tenant_id, user_id=actor_id),
                )
                year = AcademicYear(
                    tenant_id=tenant_id,
                    code="2025-26",
                    name="Synthetic Year 2025-26",
                    starts_on=date(2025, 4, 1),
                    ends_on=date(2026, 3, 31),
                )
                clazz = SchoolClass(tenant_id=tenant_id, code="8", name="Class 8")
                session.add_all([year, clazz])
                await session.flush()
                section = Section(tenant_id=tenant_id, class_id=clazz.id, name="A")
                student = Student(
                    tenant_id=tenant_id,
                    historical_subject_id=uuid4(),
                    admission_no=f"SYN-{uuid4().hex[:8]}",
                    first_name="Synthetic",
                    last_name="Student",
                    date_of_birth=date(2014, 1, 15),
                )
                guardian = Guardian(
                    tenant_id=tenant_id,
                    first_name="Synthetic",
                    last_name="Guardian",
                    phone_e164="+919876543210",
                )
                card = PhysicalCard(
                    tenant_id=tenant_id,
                    hf_uid=f"HF-{uuid4().hex[:8]}",
                    profile="uid_only",
                    status="inventory",
                )
                session.add_all([section, student, guardian, card])
                await session.flush()
                return {
                    "year_id": year.id,
                    "class_id": clazz.id,
                    "section_id": section.id,
                    "student_id": student.id,
                    "guardian_id": guardian.id,
                    "card_id": card.id,
                }

            tenant_a_data = await seed_tenant(world["tenant_a"], admin_a.id)
            tenant_b_data = await seed_tenant(world["tenant_b"], admin_b.id)

    token_a = encode_access_token(
        settings,
        user_id=admin_a.id,
        tenant_id=world["tenant_a"],
        roles=["school_admin"],
        mfa=False,
        platform=False,
    )
    token_b = encode_access_token(
        settings,
        user_id=admin_b.id,
        tenant_id=world["tenant_b"],
        roles=["school_admin"],
        mfa=False,
        platform=False,
    )
    return {
        **world,
        "admin_a": admin_a.id,
        "admin_b": admin_b.id,
        "token_a": token_a,
        "token_b": token_b,
        **{f"a_{k}": v for k, v in tenant_a_data.items()},
        **{f"b_{k}": v for k, v in tenant_b_data.items()},
    }


def auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


@pytest_asyncio.fixture
async def admin_client(client: AsyncClient, student_world: dict) -> AsyncClient:
    return client
