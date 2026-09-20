from __future__ import annotations

import csv
import hashlib
import io
from dataclasses import dataclass
from datetime import date
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from schoolpass.admin import staff as staff_admin
from schoolpass.admin.import_roster import ROSTER_COLUMNS, ROSTER_REQUIRED, apply_roster_rows, validate_roster_rows
from schoolpass.admin.import_schemas import ImportRowError, ImportValidateResponse
from schoolpass.audit.service import record_audit
from schoolpass.errors import ConflictError, ValidationFailed
from schoolpass.identity.models import AuditLog, StaffProfile, User
from schoolpass.people import services as people_svc
from schoolpass.people.models import AcademicYear, Guardian, SchoolClass, Section, Student
from schoolpass.tenancy.context import TenantContext

FORBIDDEN_COLUMNS = frozenset(
    {
        "tenant_id",
        "tenant",
        "role",
        "roles",
        "password",
        "password_hash",
        "user_id",
        "id",
        "authorization",
        "platform_role",
    }
)

IMPORT_TYPES: dict[str, frozenset[str]] = {
    "students": frozenset(
        {"admission_no", "first_name", "middle_name", "last_name", "date_of_birth"},
    ),
    "guardians": frozenset({"first_name", "last_name", "phone_e164", "email"}),
    "student_guardians": frozenset(
        {
            "admission_no",
            "guardian_email",
            "relationship_type",
            "is_primary_contact",
            "can_receive_notifications",
            "can_pay_fees",
        },
    ),
    "staff": frozenset({"email", "staff_type", "employee_code"}),
    "enrollments": frozenset(
        {"admission_no", "academic_year_code", "class_code", "section_name", "starts_on"},
    ),
    "school_roster": frozenset(ROSTER_COLUMNS),
}

REQUIRED_COLUMNS: dict[str, frozenset[str]] = {
    "students": frozenset({"admission_no", "first_name", "last_name"}),
    "guardians": frozenset({"first_name", "last_name"}),
    "student_guardians": frozenset({"admission_no", "guardian_email", "relationship_type"}),
    "staff": frozenset({"email", "staff_type"}),
    "enrollments": frozenset(
        {"admission_no", "academic_year_code", "class_code", "section_name", "starts_on"},
    ),
    "school_roster": ROSTER_REQUIRED,
}


def template_for(import_type: str) -> tuple[list[str], str]:
    if import_type not in IMPORT_TYPES:
        raise ValidationFailed("Unknown import type")
    columns = list(ROSTER_COLUMNS) if import_type == "school_roster" else sorted(IMPORT_TYPES[import_type])
    return columns, ",".join(columns)


def content_digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _tenant_id(ctx: TenantContext) -> UUID:
    if ctx.tenant_id is None:
        raise ValidationFailed("Tenant context is required")
    return ctx.tenant_id


def _parse_csv(raw: bytes, import_type: str) -> tuple[list[str], list[dict[str, str]]]:
    text = raw.decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(text))
    if reader.fieldnames is None:
        raise ValidationFailed("CSV header row is required")
    headers = [h.strip() for h in reader.fieldnames if h and h.strip()]
    if not headers:
        raise ValidationFailed("CSV header row is required")
    lower_headers = {h.lower() for h in headers}
    for forbidden in FORBIDDEN_COLUMNS:
        if forbidden in lower_headers:
            raise ValidationFailed(f"Column '{forbidden}' is not allowed in imports")
    allowed = IMPORT_TYPES[import_type]
    unknown = [h for h in headers if h not in allowed]
    if unknown:
        raise ValidationFailed(f"Unknown columns: {', '.join(sorted(unknown))}")
    missing = REQUIRED_COLUMNS[import_type] - set(headers)
    if missing:
        raise ValidationFailed(f"Missing required columns: {', '.join(sorted(missing))}")
    rows: list[dict[str, str]] = []
    for raw_row in reader:
        row = {k: (v or "").strip() for k, v in raw_row.items() if k}
        if not any(row.values()):
            continue
        rows.append(row)
    return headers, rows


def _parse_bool(value: str, *, field: str, row_number: int, errors: list[ImportRowError]) -> bool | None:
    if not value:
        return False
    lowered = value.lower()
    if lowered in {"1", "true", "yes", "y"}:
        return True
    if lowered in {"0", "false", "no", "n"}:
        return False
    errors.append(ImportRowError(row_number=row_number, message=f"{field} must be true/false"))
    return None


def _parse_date(value: str, *, field: str, row_number: int, errors: list[ImportRowError]) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        errors.append(ImportRowError(row_number=row_number, message=f"{field} must be YYYY-MM-DD"))
        return None


@dataclass
class _ParsedBatch:
    headers: list[str]
    rows: list[dict[str, str]]
    digest: str


async def _validate_students(
    session: AsyncSession,
    ctx: TenantContext,
    rows: list[dict[str, str]],
    errors: list[ImportRowError],
) -> int:
    tenant_id = _tenant_id(ctx)
    valid = 0
    seen: set[str] = set()
    for idx, row in enumerate(rows, start=2):
        admission_no = row.get("admission_no", "")
        if not admission_no:
            errors.append(ImportRowError(row_number=idx, message="admission_no is required"))
            continue
        if admission_no in seen:
            errors.append(ImportRowError(row_number=idx, message="duplicate admission_no in file"))
            continue
        seen.add(admission_no)
        if not row.get("first_name") or not row.get("last_name"):
            errors.append(ImportRowError(row_number=idx, message="first_name and last_name are required"))
            continue
        if row.get("date_of_birth"):
            if _parse_date(row["date_of_birth"], field="date_of_birth", row_number=idx, errors=errors) is None:
                continue
        existing = (
            await session.execute(
                select(Student.id).where(Student.tenant_id == tenant_id, Student.admission_no == admission_no)
            )
        ).scalar_one_or_none()
        if existing is not None:
            errors.append(ImportRowError(row_number=idx, message="student admission_no already exists"))
            continue
        valid += 1
    return valid


async def _validate_guardians(
    session: AsyncSession,
    ctx: TenantContext,
    rows: list[dict[str, str]],
    errors: list[ImportRowError],
) -> int:
    tenant_id = _tenant_id(ctx)
    valid = 0
    for idx, row in enumerate(rows, start=2):
        if not row.get("first_name") or not row.get("last_name"):
            errors.append(ImportRowError(row_number=idx, message="first_name and last_name are required"))
            continue
        email = row.get("email") or None
        if email:
            existing = (
                await session.execute(
                    select(Guardian.id).where(Guardian.tenant_id == tenant_id, Guardian.email == email)
                )
            ).scalar_one_or_none()
            if existing is not None:
                errors.append(ImportRowError(row_number=idx, message="guardian email already exists"))
                continue
        valid += 1
    return valid


async def _resolve_student(
    session: AsyncSession,
    tenant_id: UUID,
    admission_no: str,
) -> Student | None:
    return (
        await session.execute(
            select(Student).where(Student.tenant_id == tenant_id, Student.admission_no == admission_no)
        )
    ).scalar_one_or_none()


async def _resolve_guardian_by_email(
    session: AsyncSession,
    tenant_id: UUID,
    email: str,
) -> Guardian | None:
    return (
        await session.execute(
            select(Guardian).where(Guardian.tenant_id == tenant_id, Guardian.email == email)
        )
    ).scalar_one_or_none()


async def _validate_student_guardians(
    session: AsyncSession,
    ctx: TenantContext,
    rows: list[dict[str, str]],
    errors: list[ImportRowError],
) -> int:
    tenant_id = _tenant_id(ctx)
    valid = 0
    for idx, row in enumerate(rows, start=2):
        admission_no = row.get("admission_no", "")
        email = row.get("guardian_email", "")
        if not admission_no or not email:
            errors.append(ImportRowError(row_number=idx, message="admission_no and guardian_email are required"))
            continue
        student = await _resolve_student(session, tenant_id, admission_no)
        if student is None:
            errors.append(ImportRowError(row_number=idx, message="student admission_no not found in tenant"))
            continue
        guardian = await _resolve_guardian_by_email(session, tenant_id, email)
        if guardian is None:
            errors.append(ImportRowError(row_number=idx, message="guardian_email not found in tenant"))
            continue
        if not row.get("relationship_type"):
            errors.append(ImportRowError(row_number=idx, message="relationship_type is required"))
            continue
        valid += 1
    return valid


async def _validate_staff(
    session: AsyncSession,
    ctx: TenantContext,
    rows: list[dict[str, str]],
    errors: list[ImportRowError],
) -> int:
    valid = 0
    for idx, row in enumerate(rows, start=2):
        email = row.get("email", "")
        staff_type = row.get("staff_type", "")
        if not email or not staff_type:
            errors.append(ImportRowError(row_number=idx, message="email and staff_type are required"))
            continue
        if staff_type not in staff_admin.ALLOWED_STAFF_TYPES:
            errors.append(ImportRowError(row_number=idx, message="invalid staff_type"))
            continue
        user = (await session.execute(select(User).where(User.email == email))).scalar_one_or_none()
        if user is None:
            errors.append(ImportRowError(row_number=idx, message="user email not found"))
            continue
        valid += 1
    return valid


async def _resolve_academic(
    session: AsyncSession,
    tenant_id: UUID,
    *,
    year_code: str,
    class_code: str,
    section_name: str,
) -> tuple[AcademicYear, SchoolClass, Section] | None:
    year = (
        await session.execute(
            select(AcademicYear).where(AcademicYear.tenant_id == tenant_id, AcademicYear.code == year_code)
        )
    ).scalar_one_or_none()
    if year is None:
        return None
    school_class = (
        await session.execute(
            select(SchoolClass).where(SchoolClass.tenant_id == tenant_id, SchoolClass.code == class_code)
        )
    ).scalar_one_or_none()
    if school_class is None:
        return None
    section = (
        await session.execute(
            select(Section).where(
                Section.tenant_id == tenant_id,
                Section.class_id == school_class.id,
                Section.name == section_name,
            )
        )
    ).scalar_one_or_none()
    if section is None:
        return None
    return year, school_class, section


async def _validate_enrollments(
    session: AsyncSession,
    ctx: TenantContext,
    rows: list[dict[str, str]],
    errors: list[ImportRowError],
) -> int:
    tenant_id = _tenant_id(ctx)
    valid = 0
    for idx, row in enumerate(rows, start=2):
        admission_no = row.get("admission_no", "")
        if not admission_no:
            errors.append(ImportRowError(row_number=idx, message="admission_no is required"))
            continue
        student = await _resolve_student(session, tenant_id, admission_no)
        if student is None:
            errors.append(ImportRowError(row_number=idx, message="student admission_no not found in tenant"))
            continue
        starts_on = _parse_date(row.get("starts_on", ""), field="starts_on", row_number=idx, errors=errors)
        if starts_on is None and row.get("starts_on"):
            continue
        if starts_on is None:
            errors.append(ImportRowError(row_number=idx, message="starts_on is required"))
            continue
        placement = await _resolve_academic(
            session,
            tenant_id,
            year_code=row.get("academic_year_code", ""),
            class_code=row.get("class_code", ""),
            section_name=row.get("section_name", ""),
        )
        if placement is None:
            errors.append(
                ImportRowError(
                    row_number=idx,
                    message='academic_year_code, class_code, and section_name do not match tenant records',
                )
            )
            continue
        valid += 1
    return valid


async def validate_import(
    session: AsyncSession,
    ctx: TenantContext,
    *,
    import_type: str,
    raw: bytes,
) -> ImportValidateResponse:
    if import_type not in IMPORT_TYPES:
        raise ValidationFailed("Unknown import type")
    digest = content_digest(raw)
    _, rows = _parse_csv(raw, import_type)
    errors: list[ImportRowError] = []
    if import_type == "students":
        valid = await _validate_students(session, ctx, rows, errors)
    elif import_type == "guardians":
        valid = await _validate_guardians(session, ctx, rows, errors)
    elif import_type == "student_guardians":
        valid = await _validate_student_guardians(session, ctx, rows, errors)
    elif import_type == "staff":
        valid = await _validate_staff(session, ctx, rows, errors)
    elif import_type == "school_roster":
        valid = await validate_roster_rows(session, ctx, rows, errors)
    else:
        valid = await _validate_enrollments(session, ctx, rows, errors)
    return ImportValidateResponse(
        import_type=import_type,
        content_digest=digest,
        row_count=len(rows),
        valid_row_count=valid,
        errors=errors,
    )


async def apply_import(
    session: AsyncSession,
    ctx: TenantContext,
    *,
    import_type: str,
    raw: bytes,
    content_digest_expected: str,
    request_id: str | None,
) -> tuple[int, int, int]:
    digest = content_digest(raw)
    if digest != content_digest_expected:
        raise ValidationFailed("Content digest does not match validated file")
    validation = await validate_import(session, ctx, import_type=import_type, raw=raw)
    if validation.errors:
        raise ValidationFailed("Import cannot be applied until validation errors are resolved")
    _, rows = _parse_csv(raw, import_type)
    applied = 0
    skipped = 0
    tenant_id = _tenant_id(ctx)
    batch_id = uuid4()

    if import_type == "students":
        for row in rows:
            admission_no = row["admission_no"]
            existing = await _resolve_student(session, tenant_id, admission_no)
            if existing is not None:
                skipped += 1
                continue
            dob = _parse_date(row.get("date_of_birth", ""), field="date_of_birth", row_number=0, errors=[])
            await people_svc.create_student(
                session,
                ctx,
                admission_no=admission_no,
                first_name=row["first_name"],
                middle_name=row.get("middle_name") or None,
                last_name=row["last_name"],
                date_of_birth=dob,
                photo_file_id=None,
                request_id=request_id,
            )
            applied += 1
    elif import_type == "guardians":
        for row in rows:
            email = row.get("email") or None
            if email:
                existing_guardian = await _resolve_guardian_by_email(session, tenant_id, email)
                if existing_guardian is not None:
                    skipped += 1
                    continue
            await people_svc.create_guardian(
                session,
                ctx,
                first_name=row["first_name"],
                last_name=row["last_name"],
                phone_e164=row.get("phone_e164") or None,
                email=email,
                request_id=request_id,
            )
            applied += 1
    elif import_type == "student_guardians":
        for row in rows:
            student = await _resolve_student(session, tenant_id, row["admission_no"])
            guardian = await _resolve_guardian_by_email(session, tenant_id, row["guardian_email"])
            if student is None or guardian is None:
                raise ValidationFailed("Referenced student or guardian missing during apply")
            links = await people_svc.list_student_guardians(session, ctx, student.id)
            if any(link.guardian_id == guardian.id for link in links):
                skipped += 1
                continue
            await people_svc.attach_guardian(
                session,
                ctx,
                student_id=student.id,
                guardian_id=guardian.id,
                relationship_type=row["relationship_type"],
                is_primary_contact=_parse_bool(
                    row.get("is_primary_contact", ""),
                    field="is_primary_contact",
                    row_number=0,
                    errors=[],
                )
                or False,
                can_receive_notifications=_parse_bool(
                    row.get("can_receive_notifications", ""),
                    field="can_receive_notifications",
                    row_number=0,
                    errors=[],
                )
                or True,
                can_pay_fees=_parse_bool(row.get("can_pay_fees", ""), field="can_pay_fees", row_number=0, errors=[])
                or False,
                request_id=request_id,
            )
            if guardian.email:
                from schoolpass.admin.directory import ensure_user_with_role

                user = await ensure_user_with_role(
                    session, ctx, email=guardian.email, role_name="parent", phone_e164=guardian.phone_e164
                )
                if guardian.user_id != user.id:
                    guardian.user_id = user.id
            applied += 1
    elif import_type == "staff":
        for row in rows:
            user = (await session.execute(select(User).where(User.email == row["email"]))).scalar_one()
            existing_staff = (
                await session.execute(
                    select(StaffProfile).where(
                        StaffProfile.tenant_id == tenant_id,
                        StaffProfile.user_id == user.id,
                    )
                )
            ).scalar_one_or_none()
            if existing_staff is not None:
                skipped += 1
                continue
            await staff_admin.create_staff(
                session,
                ctx,
                user_id=user.id,
                staff_type=row["staff_type"],
                employee_code=row.get("employee_code") or None,
                request_id=request_id,
            )
            applied += 1
    elif import_type == "school_roster":
        applied, skipped = await apply_roster_rows(session, ctx, rows, request_id=request_id)
    else:
        for row in rows:
            student = await _resolve_student(session, tenant_id, row["admission_no"])
            if student is None:
                raise ValidationFailed("Student missing during enrollment apply")
            placement = await _resolve_academic(
                session,
                tenant_id,
                year_code=row["academic_year_code"],
                class_code=row["class_code"],
                section_name=row["section_name"],
            )
            if placement is None:
                raise ValidationFailed("Academic placement missing during apply")
            year, school_class, section = placement
            starts_on = date.fromisoformat(row["starts_on"])
            try:
                await people_svc.create_enrollment(
                    session,
                    ctx,
                    student_id=student.id,
                    academic_year_id=year.id,
                    class_id=school_class.id,
                    section_id=section.id,
                    starts_on=starts_on,
                    request_id=request_id,
                )
            except ConflictError:
                skipped += 1
                continue
            applied += 1

    status = "completed"
    await record_audit(
        session,
        ctx,
        action="import.completed",
        resource_type="import_batch",
        resource_id=batch_id,
        request_id=request_id,
        metadata={
            "import_type": import_type,
            "content_digest": digest,
            "row_count": len(rows),
            "applied_count": applied,
            "skipped_count": skipped,
            "status": status,
        },
    )
    return applied, skipped, len(rows)


async def list_import_history(
    session: AsyncSession,
    ctx: TenantContext,
    *,
    limit: int,
) -> list[dict[str, Any]]:
    tenant_id = _tenant_id(ctx)
    limit = min(max(limit, 1), 100)
    rows = (
        await session.execute(
            select(AuditLog)
            .where(
                AuditLog.tenant_id == tenant_id,
                AuditLog.resource_type == "import_batch",
            )
            .order_by(AuditLog.at.desc())
            .limit(limit)
        )
    ).scalars()
    items: list[dict[str, Any]] = []
    for row in rows:
        meta = row.metadata_ or {}
        items.append(
            {
                "id": row.id,
                "action": row.action,
                "import_type": meta.get("import_type"),
                "row_count": meta.get("row_count"),
                "status": meta.get("status"),
                "content_digest": meta.get("content_digest"),
                "created_at": row.at,
            }
        )
    return items
