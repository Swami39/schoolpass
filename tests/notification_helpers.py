from __future__ import annotations

from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from schoolpass.auth.passwords import hash_password
from schoolpass.auth.tokens import encode_access_token
from schoolpass.config import Settings
from schoolpass.db.session import apply_tenant_context
from schoolpass.identity.models import Role, TenantMembership, User
from schoolpass.people.models import Guardian, StudentGuardian
from schoolpass.tenancy.context import TenantContext


async def link_guardian_to_parent_user(
    db_factory: async_sessionmaker[AsyncSession],
    *,
    tenant_id: UUID,
    guardian_id: UUID,
    student_id: UUID,
    can_receive_notifications: bool = True,
    link_status: str = "active",
) -> dict:
    password = hash_password("correct-horse-battery")
    async with db_factory() as session:
        async with session.begin():
            await apply_tenant_context(session, TenantContext(actor_type="system", tenant_id=None, user_id=None))
            roles = {
                row.name: row
                for row in (await session.execute(select(Role).where(Role.is_system.is_(True)))).scalars()
            }
            parent_user = User(
                id=uuid4(),
                email=f"parent-{uuid4().hex[:8]}@example.invalid",
                password_hash=password,
            )
            session.add(parent_user)
            await session.flush()
            await apply_tenant_context(
                session,
                TenantContext(actor_type="user", tenant_id=tenant_id, user_id=parent_user.id),
            )
            session.add(
                TenantMembership(
                    tenant_id=tenant_id,
                    user_id=parent_user.id,
                    role_id=roles["parent"].id,
                )
            )
            guardian = await session.get(Guardian, guardian_id)
            assert guardian is not None
            guardian.user_id = parent_user.id
            link = (
                await session.execute(
                    select(StudentGuardian).where(
                        StudentGuardian.tenant_id == tenant_id,
                        StudentGuardian.student_id == student_id,
                        StudentGuardian.guardian_id == guardian_id,
                    )
                )
            ).scalar_one_or_none()
            if link is None:
                session.add(
                    StudentGuardian(
                        tenant_id=tenant_id,
                        student_id=student_id,
                        guardian_id=guardian_id,
                        relationship_type="parent",
                        can_receive_notifications=can_receive_notifications,
                        status=link_status,
                    )
                )
            else:
                link.can_receive_notifications = can_receive_notifications
                link.status = link_status
    return {"parent_user_id": parent_user.id}


def parent_token(settings: Settings, *, user_id: UUID, tenant_id: UUID) -> str:
    return encode_access_token(
        settings,
        user_id=user_id,
        tenant_id=tenant_id,
        roles=["parent"],
        mfa=False,
        platform=False,
    )
