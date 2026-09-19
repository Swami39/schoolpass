"""Teacher API test fixtures."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timezone
from uuid import UUID, uuid4

from sqlalchemy import select

from schoolpass.auth.passwords import hash_password
from schoolpass.auth.tokens import encode_access_token
from schoolpass.cards.models import CardAssignment, PhysicalCard
from schoolpass.config import Settings
from schoolpass.db.session import apply_tenant_context
from schoolpass.identity.models import ClientDevice, Role, TenantMembership, User
from schoolpass.people.models import Enrollment, Guardian, Student, StudentGuardian
from schoolpass.teacher.models import (
    Assessment,
    Subject,
    TeacherSectionAssignment,
    TimetablePeriod,
)
from schoolpass.tenancy.context import TenantContext


@dataclass
class TeacherWorld:
    tenant_id: UUID
    teacher_user_id: UUID
    teacher_token: str
    other_teacher_user_id: UUID
    other_teacher_token: str
    section_id: UUID
    class_id: UUID
    year_id: UUID
    student_id: UUID
    subject_id: UUID
    assessment_id: UUID
    client_device_id: UUID
    card_hf_uid: str
    parent_user_id: UUID


async def build_teacher_world(db_factory, student_world: dict, settings: Settings) -> TeacherWorld:
    password_hash = hash_password("correct-horse-battery")
    async with db_factory() as session:
        async with session.begin():
            await apply_tenant_context(
                session,
                TenantContext(actor_type="system", tenant_id=None, user_id=None),
            )
            roles = {
                row.name: row for row in (await session.execute(select(Role).where(Role.is_system.is_(True)))).scalars()
            }
            teacher_user = User(
                id=uuid4(),
                email=f"teacher-main-{uuid4().hex[:6]}@example.invalid",
                password_hash=password_hash,
            )
            other_teacher = User(
                id=uuid4(),
                email=f"teacher-other-{uuid4().hex[:6]}@example.invalid",
                password_hash=password_hash,
            )
            parent_user = User(
                id=uuid4(),
                email=f"parent-t-{uuid4().hex[:6]}@example.invalid",
                password_hash=password_hash,
            )
            session.add_all([teacher_user, other_teacher, parent_user])
            await session.flush()

            tenant_id = student_world["tenant_a"]
            from schoolpass.identity.models import StaffProfile

            await apply_tenant_context(
                session,
                TenantContext(actor_type="user", tenant_id=tenant_id, user_id=teacher_user.id),
            )
            session.add_all(
                [
                    TenantMembership(
                        tenant_id=tenant_id,
                        user_id=teacher_user.id,
                        role_id=roles["teacher"].id,
                    ),
                    StaffProfile(
                        tenant_id=tenant_id,
                        user_id=teacher_user.id,
                        staff_type="teacher",
                        employee_code="T-MAIN",
                    ),
                    TenantMembership(
                        tenant_id=tenant_id,
                        user_id=other_teacher.id,
                        role_id=roles["teacher"].id,
                    ),
                    StaffProfile(
                        tenant_id=tenant_id,
                        user_id=other_teacher.id,
                        staff_type="teacher",
                        employee_code="T-OTHER",
                    ),
                ]
            )
            await session.flush()

            section_id = student_world["a_section_id"]
            class_id = student_world["a_class_id"]
            year_id = student_world["a_year_id"]
            student_id = student_world["a_student_id"]
            guardian_id = student_world["a_guardian_id"]

            session.add(
                Enrollment(
                    tenant_id=tenant_id,
                    student_id=student_id,
                    academic_year_id=year_id,
                    class_id=class_id,
                    section_id=section_id,
                    status="active",
                    starts_on=date(2025, 4, 1),
                )
            )
            guardian = await session.get(Guardian, guardian_id)
            if guardian is not None:
                guardian.user_id = parent_user.id
            session.add(
                StudentGuardian(
                    tenant_id=tenant_id,
                    student_id=student_id,
                    guardian_id=guardian_id,
                    relationship_type="parent",
                    status="active",
                )
            )
            subject = Subject(tenant_id=tenant_id, code="MATH", name="Mathematics")
            session.add(subject)
            await session.flush()

            session.add(
                TeacherSectionAssignment(
                    tenant_id=tenant_id,
                    teacher_user_id=teacher_user.id,
                    academic_year_id=year_id,
                    section_id=section_id,
                    subject_id=subject.id,
                    assignment_role="class_teacher",
                    status="active",
                )
            )
            assessment = Assessment(
                tenant_id=tenant_id,
                academic_year_id=year_id,
                section_id=section_id,
                subject_id=subject.id,
                code="UT1",
                name="Unit Test 1",
                max_marks=50,
                scheduled_on=date(2025, 9, 1),
            )
            session.add(assessment)
            session.add(
                TimetablePeriod(
                    tenant_id=tenant_id,
                    academic_year_id=year_id,
                    section_id=section_id,
                    day_of_week=1,
                    period_number=1,
                    starts_at=time(9, 0),
                    ends_at=time(9, 45),
                    subject_id=subject.id,
                    teacher_user_id=teacher_user.id,
                )
            )
            card = PhysicalCard(
                tenant_id=tenant_id,
                hf_uid=f"HFTEACH{uuid4().hex[:8]}",
                profile="uid_only",
                status="active",
            )
            session.add(card)
            await session.flush()
            issued = datetime(2025, 4, 1, tzinfo=timezone.utc)
            session.add(
                CardAssignment(
                    tenant_id=tenant_id,
                    student_id=student_id,
                    physical_card_id=card.id,
                    status="active",
                    issued_at=issued,
                    activated_at=issued,
                )
            )
            device = ClientDevice(
                user_id=teacher_user.id,
                device_uuid=uuid4(),
                app_flavor="teacher",
                status="active",
            )
            session.add(device)
            await session.flush()

    token = encode_access_token(
        settings,
        user_id=teacher_user.id,
        tenant_id=tenant_id,
        roles=["teacher"],
        mfa=False,
        platform=False,
    )
    other_token = encode_access_token(
        settings,
        user_id=other_teacher.id,
        tenant_id=tenant_id,
        roles=["teacher"],
        mfa=False,
        platform=False,
    )
    return TeacherWorld(
        tenant_id=tenant_id,
        teacher_user_id=teacher_user.id,
        teacher_token=token,
        other_teacher_user_id=other_teacher.id,
        other_teacher_token=other_token,
        section_id=section_id,
        class_id=class_id,
        year_id=year_id,
        student_id=student_id,
        subject_id=subject.id,
        assessment_id=assessment.id,
        client_device_id=device.id,
        card_hf_uid=card.hf_uid,
        parent_user_id=parent_user.id,
    )
