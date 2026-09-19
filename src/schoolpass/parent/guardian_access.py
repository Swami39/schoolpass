"""Guardian linkage checks for parent-scoped APIs."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from schoolpass.errors import NotFoundError
from schoolpass.people.models import Guardian, StudentGuardian


async def load_guardian_for_user(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    user_id: UUID,
) -> Guardian:
    row = (
        await session.execute(
            select(Guardian).where(
                Guardian.tenant_id == tenant_id,
                Guardian.user_id == user_id,
                Guardian.status == "active",
            )
        )
    ).scalar_one_or_none()
    if row is None:
        raise NotFoundError()
    return row


async def assert_guardian_linked_to_student(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    guardian_id: UUID,
    student_id: UUID,
) -> None:
    link = (
        await session.execute(
            select(StudentGuardian.id).where(
                StudentGuardian.tenant_id == tenant_id,
                StudentGuardian.guardian_id == guardian_id,
                StudentGuardian.student_id == student_id,
                StudentGuardian.status == "active",
            )
        )
    ).scalar_one_or_none()
    if link is None:
        raise NotFoundError()


async def assert_user_linked_to_student(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    user_id: UUID,
    student_id: UUID,
) -> Guardian:
    guardian = await load_guardian_for_user(session, tenant_id=tenant_id, user_id=user_id)
    await assert_guardian_linked_to_student(
        session,
        tenant_id=tenant_id,
        guardian_id=guardian.id,
        student_id=student_id,
    )
    return guardian
