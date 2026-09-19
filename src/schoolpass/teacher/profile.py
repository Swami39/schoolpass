"""Teacher profile summary."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from schoolpass.errors import NotFoundError
from schoolpass.identity.models import User
from schoolpass.teacher.access import load_teacher_staff
from schoolpass.tenancy.context import TenantContext


@dataclass(frozen=True)
class TeacherMeSummary:
    user_id: UUID
    email: str | None
    employee_code: str | None


async def get_teacher_me(session: AsyncSession, ctx: TenantContext) -> TeacherMeSummary:
    if ctx.tenant_id is None or ctx.user_id is None:
        raise NotFoundError()
    staff = await load_teacher_staff(session, tenant_id=ctx.tenant_id, user_id=ctx.user_id)
    user = await session.get(User, ctx.user_id)
    if user is None:
        raise NotFoundError()
    return TeacherMeSummary(
        user_id=user.id,
        email=user.email,
        employee_code=staff.employee_code,
    )
