"""Admin CSV imports — Phase 10D."""

from __future__ import annotations

from uuid import uuid4

import pytest

from admin_helpers import AdminWorld, build_admin_world
from fixtures_students import auth_headers


@pytest.fixture
async def admin_world(db_factory, world, settings) -> AdminWorld:
    return await build_admin_world(db_factory, settings=settings, base_world=world)


def _multipart_csv(content: str) -> tuple[str, bytes, str]:
    return ("file", content.encode("utf-8"), "text/csv")


async def test_import_rejects_tenant_id_column(client, admin_world) -> None:
    headers = auth_headers(admin_world.admin_token)
    csv_body = "admission_no,first_name,last_name,tenant_id\nA1,Ada,Lovelace,evil\n"
    response = await client.post(
        "/api/v1/admin/imports/students/validate",
        headers=headers,
        files={"file": _multipart_csv(csv_body)},
    )
    assert response.status_code in {400, 422}
    detail = response.text.lower()
    assert "tenant_id" in detail or "not allowed" in detail


async def test_student_import_validate_and_apply(client, admin_world) -> None:
    headers = auth_headers(admin_world.admin_token)
    csv_body = "admission_no,first_name,last_name\nIMP-001,Import,Student\n"
    validated = await client.post(
        "/api/v1/admin/imports/students/validate",
        headers=headers,
        files={"file": _multipart_csv(csv_body)},
    )
    assert validated.status_code == 200
    body = validated.json()
    assert body["valid_row_count"] == 1
    assert body["errors"] == []
    digest = body["content_digest"]
    applied = await client.post(
        "/api/v1/admin/imports/students/apply",
        headers=headers,
        data={"confirm": "true", "content_digest": digest},  # multipart form fields
        files={"file": _multipart_csv(csv_body)},
    )
    assert applied.status_code == 200
    assert applied.json()["applied_count"] == 1
    history = await client.get("/api/v1/admin/imports/history", headers=headers)
    assert history.status_code == 200
    assert len(history.json()["items"]) >= 1


async def test_teacher_denied_imports(client, admin_world) -> None:
    headers = auth_headers(admin_world.teacher_token)
    response = await client.get("/api/v1/admin/imports/types/students/template", headers=headers)
    assert response.status_code == 403


async def test_import_idempotent_retry(client, admin_world) -> None:
    headers = auth_headers(admin_world.admin_token)
    csv_body = "admission_no,first_name,last_name\nIMP-002,Retry,Student\n"
    first = await client.post(
        "/api/v1/admin/imports/students/validate",
        headers=headers,
        files={"file": _multipart_csv(csv_body)},
    )
    digest = first.json()["content_digest"]
    await client.post(
        "/api/v1/admin/imports/students/apply",
        headers=headers,
        data={"confirm": "true", "content_digest": digest},  # multipart form fields
        files={"file": _multipart_csv(csv_body)},
    )
    # Re-validate fails because student exists
    second_validate = await client.post(
        "/api/v1/admin/imports/students/validate",
        headers=headers,
        files={"file": _multipart_csv(csv_body)},
    )
    assert second_validate.status_code == 200
    assert second_validate.json()["valid_row_count"] == 0


async def test_school_roster_import_links_parent_login(client, admin_world, db_factory) -> None:
    headers = auth_headers(admin_world.admin_token)
    suffix = uuid4().hex[:8]
    csv_body = (
        "academic_year_code,academic_year_name,year_starts_on,year_ends_on,class_code,class_name,section_name,"
        "teacher_email,subject_code,subject_name,admission_no,student_first_name,student_middle_name,"
        "student_last_name,student_dob,parent_email,parent_first_name,parent_last_name,parent_phone,relationship_type\n"
        f"2026-27,AY 2026-27,2026-04-01,2027-03-31,8,Class 8,B,teacher-{suffix}@example.invalid,SCI,Science,"
        f"ADM-{suffix},Isha,,Mehta,2015-01-15,parent-{suffix}@example.invalid,Amit,Mehta,,parent\n"
    )
    validated = await client.post(
        "/api/v1/admin/imports/school_roster/validate",
        headers=headers,
        files={"file": _multipart_csv(csv_body)},
    )
    assert validated.status_code == 200, validated.text
    assert validated.json()["errors"] == []
    digest = validated.json()["content_digest"]
    applied = await client.post(
        "/api/v1/admin/imports/school_roster/apply",
        headers=headers,
        data={"confirm": "true", "content_digest": digest},
        files={"file": _multipart_csv(csv_body)},
    )
    assert applied.status_code == 200, applied.text
    assert applied.json()["applied_count"] == 1

    students = await client.get(
        "/api/v1/admin/students",
        headers=headers,
        params={"search": f"ADM-{suffix}"},
    )
    assert students.status_code == 200
    items = students.json()["items"]
    assert any(s["admission_no"] == f"ADM-{suffix}" for s in items)
    student_id = next(s["id"] for s in items if s["admission_no"] == f"ADM-{suffix}")
    links = await client.get(f"/api/v1/admin/students/{student_id}/guardians", headers=headers)
    assert links.status_code == 200
    assert links.json()["items"]
    guardian_id = links.json()["items"][0]["guardian_id"]
    guardian = await client.get(f"/api/v1/admin/guardians/{guardian_id}", headers=headers)
    assert guardian.status_code == 200
    assert guardian.json()["email"] == f"parent-{suffix}@example.invalid"
    assert guardian.json()["user_id"]


async def test_create_guardian_provisions_parent_login(client, admin_world, db_factory) -> None:
    headers = auth_headers(admin_world.admin_token)
    email = f"new-parent-{uuid4().hex[:8]}@example.invalid"
    created = await client.post(
        "/api/v1/admin/guardians",
        headers=headers,
        json={"first_name": "Priya", "last_name": "Nair", "email": email, "create_parent_login": True},
    )
    assert created.status_code == 200, created.text
    body = created.json()
    assert body["email"] == email
    assert body["user_id"]

    from sqlalchemy import select

    from schoolpass.identity.models import User

    async with db_factory() as session:
        user = (await session.execute(select(User).where(User.email == email))).scalar_one()
        assert user.id is not None
        assert user.password_hash is not None

