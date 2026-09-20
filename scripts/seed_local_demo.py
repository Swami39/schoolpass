#!/usr/bin/env python3
"""Development-only synthetic dataset for local stack smoke tests.

Run: python scripts/seed_local_demo.py
Idempotent on slug `schoolpass-demo-local`.
"""

from __future__ import annotations

import asyncio
import json
from datetime import date
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

from sqlalchemy import select

from schoolpass.auth.crypto import encrypt_secret
from schoolpass.auth.passwords import hash_password
from schoolpass.cards.models import PhysicalCard
from schoolpass.config import get_settings
from schoolpass.db.session import apply_tenant_context, create_engine, session_factory
from schoolpass.identity.models import Role, StaffProfile, Tenant, TenantMembership, User
from schoolpass.people.models import (
    AcademicYear,
    Enrollment,
    Guardian,
    SchoolClass,
    Section,
    Student,
    StudentGuardian,
)
from schoolpass.teacher.models import Subject, TeacherSectionAssignment
from schoolpass.tenancy.context import TenantContext
from schoolpass.transport.models import Trip
from schoolpass.transport.services import (
    add_route_stop,
    create_bus,
    create_route,
    create_transport_assignment,
    create_transport_attendant,
    create_trip,
)

DEMO_SLUG = "schoolpass-demo-local"
DEMO_PASSWORD = "Demo-Local-Only-2026"
# Development-only TOTP secret for school_admin MFA (required for that role).
DEV_ADMIN_MFA_SECRET = "JBSWY3DPEHPK3PXP"
CREDENTIALS_PATH = Path(".data/local_demo_credentials.json")

DEMO_USER_EMAILS = {
    "school_admin": "demo.admin@schoolpass.local",
    "teacher": "demo.teacher@schoolpass.local",
    "parent": "demo.parent@schoolpass.local",
    "attendant": "demo.attendant@schoolpass.local",
}


async def _write_credentials(tenant_id, trip_id: str | None = None) -> None:
    creds = {
        "tenant_id": str(tenant_id),
        "tenant_slug": DEMO_SLUG,
        "password": DEMO_PASSWORD,
        "users": DEMO_USER_EMAILS,
        "students": ["demo.student001", "demo.student002"],
        "trip_id": trip_id,
        "admin_mfa_secret": DEV_ADMIN_MFA_SECRET,
    }
    CREDENTIALS_PATH.parent.mkdir(parents=True, exist_ok=True)
    CREDENTIALS_PATH.write_text(json.dumps(creds, indent=2))
    print(json.dumps(creds, indent=2))


async def repair_demo_tenant(session, tenant: Tenant) -> None:
    """Idempotent fixes for local demo data created before full seed completed."""
    tenant_id = tenant.id
    ctx = TenantContext(actor_type="system", tenant_id=tenant_id, user_id=None)
    await apply_tenant_context(session, ctx)

    users: dict[str, User] = {}
    for role, email in DEMO_USER_EMAILS.items():
        row = (await session.execute(select(User).where(User.email == email))).scalar_one_or_none()
        if row is not None:
            users[role] = row

    parent_user = users.get("parent")
    if parent_user is not None:
        guardian = (
            await session.execute(
                select(Guardian).where(
                    Guardian.tenant_id == tenant_id,
                    Guardian.email == DEMO_USER_EMAILS["parent"],
                )
            )
        ).scalar_one_or_none()
        if guardian is not None and guardian.user_id != parent_user.id:
            guardian.user_id = parent_user.id

    teacher_user = users.get("teacher")
    if teacher_user is not None:
        has_assignment = (
            await session.execute(
                select(TeacherSectionAssignment.id).where(
                    TeacherSectionAssignment.tenant_id == tenant_id,
                    TeacherSectionAssignment.teacher_user_id == teacher_user.id,
                    TeacherSectionAssignment.status == "active",
                )
            )
        ).scalar_one_or_none()
        if has_assignment is None:
            year = (
                await session.execute(
                    select(AcademicYear)
                    .where(AcademicYear.tenant_id == tenant_id, AcademicYear.status == "active")
                    .limit(1)
                )
            ).scalar_one_or_none()
            section = (
                await session.execute(
                    select(Section).where(Section.tenant_id == tenant_id, Section.status == "active").limit(1)
                )
            ).scalar_one_or_none()
            subject = (
                await session.execute(
                    select(Subject).where(Subject.tenant_id == tenant_id, Subject.status == "active").limit(1)
                )
            ).scalar_one_or_none()
            if subject is None and year is not None:
                subject = Subject(tenant_id=tenant_id, code="MATH", name="Mathematics")
                session.add(subject)
                await session.flush()
            if year is not None and section is not None:
                session.add(
                    TeacherSectionAssignment(
                        tenant_id=tenant_id,
                        teacher_user_id=teacher_user.id,
                        academic_year_id=year.id,
                        section_id=section.id,
                        subject_id=subject.id if subject is not None else None,
                        assignment_role="class_teacher",
                    )
                )

    trip_id = (
        await session.execute(select(Trip.id).where(Trip.tenant_id == tenant_id).limit(1))
    ).scalar_one_or_none()
    await _write_credentials(tenant_id, str(trip_id) if trip_id else None)


async def main() -> None:
    settings = get_settings()
    engine = create_engine(settings.database_url, null_pool=True)
    factory = session_factory(engine)
    password_hash = hash_password(DEMO_PASSWORD)

    async with factory() as session:
        async with session.begin():
            await apply_tenant_context(session, TenantContext(actor_type="system", tenant_id=None, user_id=None))
            existing = (
                await session.execute(select(Tenant).where(Tenant.slug == DEMO_SLUG))
            ).scalar_one_or_none()
            if existing is not None:
                print(f"Demo tenant already exists: {existing.id} (slug={DEMO_SLUG}); repairing local links")
                await repair_demo_tenant(session, existing)
                await engine.dispose()
                return

            roles = {
                row.name: row
                for row in (await session.execute(select(Role).where(Role.is_system.is_(True)))).scalars()
            }
            tenant = Tenant(
                id=uuid4(),
                legal_name="SchoolPass Demo School",
                display_name="SchoolPass Demo School",
                slug=DEMO_SLUG,
                contact_email="office@demo.schoolpass.local",
                city="Chennai",
            )
            session.add(tenant)
            await session.flush()
            tenant_id = tenant.id

            users = {
                "admin": User(
                    id=uuid4(),
                    email="demo.admin@schoolpass.local",
                    password_hash=password_hash,
                ),
                "teacher": User(
                    id=uuid4(),
                    email="demo.teacher@schoolpass.local",
                    password_hash=password_hash,
                ),
                "parent": User(
                    id=uuid4(),
                    email="demo.parent@schoolpass.local",
                    password_hash=password_hash,
                ),
                "attendant": User(
                    id=uuid4(),
                    email="demo.attendant@schoolpass.local",
                    password_hash=password_hash,
                ),
            }
            session.add_all(users.values())
            await session.flush()
            admin_user = users["admin"]
            admin_user.mfa_enabled = True
            admin_user.mfa_secret_encrypted = encrypt_secret(settings, DEV_ADMIN_MFA_SECRET)

            ctx = TenantContext(actor_type="user", tenant_id=tenant_id, user_id=users["admin"].id)
            await apply_tenant_context(session, ctx)

            session.add(
                TenantMembership(
                    tenant_id=tenant_id,
                    user_id=users["admin"].id,
                    role_id=roles["school_admin"].id,
                )
            )
            session.add(
                TenantMembership(
                    tenant_id=tenant_id,
                    user_id=users["teacher"].id,
                    role_id=roles["teacher"].id,
                )
            )
            session.add(
                StaffProfile(
                    tenant_id=tenant_id,
                    user_id=users["teacher"].id,
                    staff_type="teacher",
                    employee_code="demo.teacher001",
                )
            )
            session.add(
                TenantMembership(
                    tenant_id=tenant_id,
                    user_id=users["parent"].id,
                    role_id=roles["parent"].id,
                )
            )
            session.add(
                TenantMembership(
                    tenant_id=tenant_id,
                    user_id=users["attendant"].id,
                    role_id=roles["bus_attendant"].id,
                )
            )
            session.add(
                StaffProfile(
                    tenant_id=tenant_id,
                    user_id=users["attendant"].id,
                    staff_type="bus_attendant",
                    employee_code="demo.attendant001",
                )
            )
            await session.flush()

            year = AcademicYear(
                tenant_id=tenant_id,
                code="2026-27",
                name="Academic Year 2026-27",
                starts_on=date(2026, 4, 1),
                ends_on=date(2027, 3, 31),
            )
            clazz = SchoolClass(tenant_id=tenant_id, code="10", name="Class 10")
            session.add_all([year, clazz])
            await session.flush()
            section = Section(tenant_id=tenant_id, class_id=clazz.id, name="A")
            math = Subject(tenant_id=tenant_id, code="MATH", name="Mathematics")
            science = Subject(tenant_id=tenant_id, code="SCI", name="Science")
            session.add_all([section, math, science])
            await session.flush()

            students = []
            for i in (1, 2):
                students.append(
                    Student(
                        tenant_id=tenant_id,
                        historical_subject_id=uuid4(),
                        admission_no=f"demo.student00{i}",
                        first_name=f"Demo{i}",
                        last_name="Student",
                        date_of_birth=date(2014, 6, i),
                    )
                )
            guardians = [
                Guardian(
                    tenant_id=tenant_id,
                    first_name="Demo",
                    last_name="Parent",
                    email="demo.parent@schoolpass.local",
                    phone_e164="+919000000001",
                    user_id=users["parent"].id,
                ),
                Guardian(
                    tenant_id=tenant_id,
                    first_name="Demo",
                    last_name="Parent2",
                    email="demo.parent2@schoolpass.local",
                    phone_e164="+919000000002",
                ),
            ]
            card = PhysicalCard(
                tenant_id=tenant_id,
                hf_uid="DEMO-HF-00000001",
                uhf_epc="DEMO-EPC-00000001",
                profile="uid_only",
                status="inventory",
            )
            session.add_all([*students, *guardians, card])
            await session.flush()

            for student in students:
                session.add(
                    Enrollment(
                        tenant_id=tenant_id,
                        student_id=student.id,
                        academic_year_id=year.id,
                        class_id=clazz.id,
                        section_id=section.id,
                        starts_on=date(2026, 4, 1),
                    )
                )
                session.add(
                    StudentGuardian(
                        tenant_id=tenant_id,
                        student_id=student.id,
                        guardian_id=guardians[0].id,
                        relationship_type="parent",
                        is_primary_contact=True,
                    )
                )
            session.add(
                TeacherSectionAssignment(
                    tenant_id=tenant_id,
                    teacher_user_id=users["teacher"].id,
                    academic_year_id=year.id,
                    section_id=section.id,
                    subject_id=math.id,
                    assignment_role="class_teacher",
                )
            )
            await session.flush()

            bus = await create_bus(
                session,
                ctx,
                registration_number="TN-DEMO-0001",
                fleet_number="BUS-1",
                display_name="Demo Bus 1",
                capacity=40,
                request_id="seed",
            )
            route = await create_route(
                session,
                ctx,
                name="Demo Route Pickup",
                code="DEMO-R1",
                direction="pickup",
                request_id="seed",
            )
            stop = await add_route_stop(
                session,
                ctx,
                route.id,
                name="Demo Stop A",
                sequence=1,
                latitude=Decimal("12.971600"),
                longitude=Decimal("77.594600"),
                request_id="seed",
            )
            attendant = await create_transport_attendant(
                session,
                ctx,
                user_id=users["attendant"].id,
                employee_code="demo.attendant001",
                request_id="seed",
            )
            await create_transport_assignment(
                session,
                ctx,
                student_id=students[0].id,
                route_id=route.id,
                stop_id=stop.id,
                effective_from=date(2026, 4, 1),
                request_id="seed",
            )
            trip = await create_trip(
                session,
                ctx,
                bus_id=bus.id,
                route_id=route.id,
                attendant_id=attendant.id,
                service_date=date.today(),
                shift="pickup",
                request_id="seed",
            )

    await _write_credentials(tenant_id, str(trip.id))
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
