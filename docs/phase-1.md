# Phase 1 implementation notes

This document records decisions taken while implementing the backend foundation.
It does not replace the architecture set.

## Schema implemented

Platform (no tenant RLS): `tenants`, `users`, `permissions`, `role_permissions`,
`platform_memberships`, `refresh_tokens`, `client_devices`, `outbox`.

`outbox` is an infrastructure table. The publisher must `SELECT` unpublished rows
across tenants. Payloads are identifiers only. This is an intentional RLS exception
documented in architecture as hybrid/internal.

Hybrid RLS:
- `roles`: visible when `tenant_id IS NULL` (system roles) or matches GUC.
- `audit_logs`: `tenant_id IS NULL` or matches GUC; app role INSERT/SELECT only.
- `tenant_memberships`: tenant GUC **or** `user_id = app.user_id` for SELECT so login
  can list a user's schools. `WITH CHECK` still requires tenant GUC.

Strict FORCE RLS: `staff_profiles`.

`platform_memberships` holds `platform_*` roles (no tenant). Architecture assigns
those roles without a school membership.

Student, card, RFID, GPS, payment, and notification tables are **not** in Phase 1.
RLS isolation tests use `staff_profiles` as the tenant-owned relation.

## Auth

- Argon2id passwords, RS256 access JWT (~10 minutes), hashed rotating refresh tokens.
- OTP: hashed in Redis. `OTP_DEV_ALLOW` may capture codes in Redis for local/test only.
  Production raises if a delivery provider is not configured.
- MFA TOTP enrollment/verify is implemented. `school_admin` and `platform_*` require MFA
  (enrollment challenge on login until enabled).

## Adapters

- Redis: required for readiness and OTP rate limits.
- Service Bus: `SERVICE_BUS_MODE=local` publishes identifier envelopes to Redis lists.
  `azure` mode refuses to pretend success until workload identity is configured.
- Blob: local filesystem under `BLOB_LOCAL_ROOT`.
- Metrics and tracing are in-process hooks only; no fake remote telemetry backend.

## Commands

```bash
docker compose -f infra/docker/compose.yaml up -d
python scripts/gen_dev_keys.py  # set JWT_* in .env
alembic upgrade head
uvicorn schoolpass.api.main:app --reload
python -m schoolpass.worker.main
pytest
```
