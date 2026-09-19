from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from schoolpass.auth.passwords import hash_password
from schoolpass.auth.tokens import encode_access_token
from schoolpass.config import Settings
from schoolpass.db.session import apply_tenant_context
from schoolpass.identity.models import Role, TenantMembership, User
from schoolpass.tenancy.context import TenantContext


@dataclass
class AdminWorld:
    tenant_id: UUID
    other_tenant_id: UUID
    admin_user_id: UUID
    teacher_user_id: UUID
    admin_token: str
    teacher_token: str
    admin_email: str


async def build_admin_world(
    db_factory: async_sessionmaker,
    *,
    settings: Settings,
    base_world: dict[str, UUID],
) -> AdminWorld:
    password = hash_password("correct-horse-battery")
    async with db_factory() as session:
        async with session.begin():
            await apply_tenant_context(session, TenantContext(actor_type="system", tenant_id=None, user_id=None))
            roles = {
                row.name: row for row in (await session.execute(select(Role).where(Role.is_system.is_(True)))).scalars()
            }
            admin_user = User(
                id=uuid4(),
                email=f"admin-{uuid4().hex[:6]}@example.invalid",
                password_hash=password,
            )
            teacher_user = User(
                id=uuid4(),
                email=f"staff-{uuid4().hex[:6]}@example.invalid",
                password_hash=password,
            )
            session.add_all([admin_user, teacher_user])
            await session.flush()
            tenant_a = base_world["tenant_a"]
            tenant_b = base_world["tenant_b"]
            await apply_tenant_context(
                session,
                TenantContext(actor_type="user", tenant_id=tenant_a, user_id=admin_user.id),
            )
            session.add_all(
                [
                    TenantMembership(
                        tenant_id=tenant_a,
                        user_id=admin_user.id,
                        role_id=roles["school_admin"].id,
                    ),
                    TenantMembership(
                        tenant_id=tenant_a,
                        user_id=teacher_user.id,
                        role_id=roles["teacher"].id,
                    ),
                ]
            )
            await session.flush()

    admin_token = encode_access_token(
        settings,
        user_id=admin_user.id,
        tenant_id=tenant_a,
        roles=["school_admin"],
        mfa=False,
        platform=False,
    )
    teacher_token = encode_access_token(
        settings,
        user_id=teacher_user.id,
        tenant_id=tenant_a,
        roles=["teacher"],
        mfa=False,
        platform=False,
    )
    return AdminWorld(
        tenant_id=tenant_a,
        other_tenant_id=tenant_b,
        admin_user_id=admin_user.id,
        teacher_user_id=teacher_user.id,
        admin_token=admin_token,
        teacher_token=teacher_token,
        admin_email=admin_user.email or "",
    )
