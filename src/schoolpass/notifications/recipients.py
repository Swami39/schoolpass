from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from schoolpass.people.models import Guardian, StudentGuardian


async def list_guardian_recipient_user_ids(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    student_id: UUID,
) -> list[UUID]:
    """Resolve parent/guardian user accounts eligible for operational notifications."""
    stmt = (
        select(Guardian.user_id)
        .join(
            StudentGuardian,
            (StudentGuardian.guardian_id == Guardian.id)
            & (StudentGuardian.tenant_id == Guardian.tenant_id),
        )
        .where(
            StudentGuardian.tenant_id == tenant_id,
            StudentGuardian.student_id == student_id,
            StudentGuardian.status == "active",
            StudentGuardian.can_receive_notifications.is_(True),
            Guardian.status == "active",
            Guardian.user_id.is_not(None),
        )
        .distinct()
    )
    rows = (await session.execute(stmt)).scalars().all()
    return [uid for uid in rows if uid is not None]
