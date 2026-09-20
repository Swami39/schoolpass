#!/usr/bin/env python3
"""HTTP smoke test against a running local API (default http://127.0.0.1:8000)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import httpx
import pyotp

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000"
CREDS = json.loads(Path(".data/local_demo_credentials.json").read_text())


def login(email: str) -> dict[str, str]:
    r = httpx.post(
        f"{BASE}/api/v1/auth/password/login",
        json={
            "identifier": email,
            "password": CREDS["password"],
            "tenant_id": CREDS["tenant_id"],
        },
        timeout=30.0,
    )
    r.raise_for_status()
    body = r.json()
    if body.get("mfa_required"):
        secret = CREDS.get("admin_mfa_secret")
        if not secret:
            raise RuntimeError(f"MFA required for {email} but no admin_mfa_secret in credentials")
        code = pyotp.TOTP(secret).now()
        mfa = httpx.post(
            f"{BASE}/api/v1/auth/mfa/verify",
            json={
                "mfa_token": body["mfa_token"],
                "code": code,
                "tenant_id": CREDS["tenant_id"],
            },
            timeout=30.0,
        )
        mfa.raise_for_status()
        body = mfa.json()
    if "access_token" not in body:
        raise RuntimeError(f"login failed for {email}: {body}")
    return {"Authorization": f"Bearer {body['access_token']}"}


def check(name: str, r: httpx.Response, ok: set[int] = {200}) -> None:
    if r.status_code not in ok:
        raise AssertionError(f"{name}: {r.status_code} {r.text[:500]}")


def main() -> None:
    live = httpx.get(f"{BASE}/health/live", timeout=10.0)
    ready = httpx.get(f"{BASE}/health/ready", timeout=10.0)
    check("health/live", live)
    check("health/ready", ready)
    print("health: ok")

    admin_h = login(CREDS["users"]["school_admin"])
    teacher_h = login(CREDS["users"]["teacher"])
    parent_h = login(CREDS["users"]["parent"])
    attendant_h = login(CREDS["users"]["attendant"])
    print("auth: all roles logged in")

    endpoints_admin = [
        "/api/v1/admin/school",
        "/api/v1/admin/academic-years",
        "/api/v1/admin/classes",
        "/api/v1/admin/sections",
        "/api/v1/admin/subjects",
        "/api/v1/admin/teacher-assignments",
        "/api/v1/admin/students",
        "/api/v1/admin/guardians",
        "/api/v1/admin/enrollments",
        "/api/v1/admin/staff",
        "/api/v1/admin/cards",
        "/api/v1/admin/rfid-readers",
        "/api/v1/admin/rfid-events",
        "/api/v1/admin/buses",
        "/api/v1/admin/trips",
        "/api/v1/admin/transport-assignments",
        "/api/v1/admin/transport-attendants",
        "/api/v1/admin/routes",
        "/api/v1/admin/boarding-records",
        "/api/v1/admin/location-samples",
        "/api/v1/admin/operations/overview",
        "/api/v1/admin/imports/types/students/template",
    ]
    for path in endpoints_admin:
        r = httpx.get(f"{BASE}{path}", headers=admin_h, timeout=30.0)
        check(f"admin GET {path}", r)

    bad_login = httpx.post(
        f"{BASE}/api/v1/auth/password/login",
        json={"identifier": CREDS["users"]["school_admin"], "password": "wrong", "tenant_id": CREDS["tenant_id"]},
    )
    if bad_login.status_code not in {401, 403}:
        raise AssertionError(f"bad login expected 401/403 got {bad_login.status_code}")

    teacher_write = httpx.post(
        f"{BASE}/api/v1/admin/students",
        headers=teacher_h,
        json={"admission_no": "x", "first_name": "X", "last_name": "Y"},
    )
    if teacher_write.status_code != 403:
        raise AssertionError(f"teacher admin write expected 403 got {teacher_write.status_code}")

    parent_admin = httpx.get(f"{BASE}/api/v1/admin/students", headers=parent_h)
    if parent_admin.status_code != 403:
        raise AssertionError(f"parent admin expected 403 got {parent_admin.status_code}")

    teacher_me = httpx.get(f"{BASE}/api/v1/teacher/me", headers=teacher_h)
    check("teacher me", teacher_me)
    teacher_classes = httpx.get(f"{BASE}/api/v1/teacher/classes", headers=teacher_h)
    check("teacher classes", teacher_classes)

    parent_children = httpx.get(f"{BASE}/api/v1/parent/children", headers=parent_h)
    check("parent children", parent_children)

    csv = "admission_no,first_name,last_name\nsmoke.tmp,Smoke,Row\n"
    validate = httpx.post(
        f"{BASE}/api/v1/admin/imports/students/validate",
        headers=admin_h,
        files={"file": ("smoke.csv", csv.encode(), "text/csv")},
        timeout=30.0,
    )
    check("import validate", validate)
    digest = validate.json()["content_digest"]
    deny = httpx.post(
        f"{BASE}/api/v1/admin/imports/students/apply",
        headers=admin_h,
        data={"confirm": "false", "content_digest": digest},
        files={"file": ("smoke.csv", csv.encode(), "text/csv")},
    )
    if deny.status_code not in {400, 422}:
        raise AssertionError(f"import confirm=false expected 400/422 got {deny.status_code}")

    print("smoke_local_stack: ALL CHECKS PASSED")


if __name__ == "__main__":
    main()
