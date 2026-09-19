"""Parent-facing linked children queries."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from schoolpass.errors import NotFoundError
from schoolpass.parent.guardian_access import load_guardian_for_user
from schoolpass.people.models import Student, StudentGuardian
from schoolpass.tenancy.context import TenantContext


@dataclass(frozen=True)
class ParentChildSummary:
    student_id: UUID
    first_name: str
    middle_name: str | None
    last_name: str
    admission_no: str
    status: str


async def list_linked_children(
    session: AsyncSession,
    ctx: TenantContext,
) -> list[ParentChildSummary]:
    if ctx.tenant_id is None or ctx.user_id is None:
        raise NotFoundError()
    tenant_id = ctx.tenant_id
    guardian = await load_guardian_for_user(session, tenant_id=tenant_id, user_id=ctx.user_id)
    rows = (
        await session.execute(
            select(Student)
            .join(
                StudentGuardian,
                (StudentGuardian.student_id == Student.id)
                & (StudentGuardian.tenant_id == Student.tenant_id),
            )
            .where(
                StudentGuardian.tenant_id == tenant_id,
                StudentGuardian.guardian_id == guardian.id,
                StudentGuardian.status == "active",
                Student.status == "active",
            )
            .order_by(Student.last_name, Student.first_name, Student.admission_no)
        )
    ).scalars().all()
    return [
        ParentChildSummary(
            student_id=row.id,
            first_name=row.first_name,
            middle_name=row.middle_name,
            last_name=row.last_name,
            admission_no=row.admission_no,
            status=row.status,
        )
        for row in rows
    ]
