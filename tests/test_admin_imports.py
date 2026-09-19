"""Admin CSV imports — Phase 10D."""

from __future__ import annotations

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
