# SchoolPass

Production SaaS for schools: dual-frequency (HF + UHF) student cards, gate attendance, bus boarding with offline sync, GPS, parent communication, academics, and UPI fees.

**Phase 1** is the backend foundation (FastAPI, PostgreSQL RLS, auth, audit, outbox). **Phase 2** adds students, guardians, enrollments, and academic structure. Product domains (RFID, NFC, GPS, fees, apps) are not implemented yet.

## Local development

```bash
cp .env.example .env
docker compose -f infra/docker/compose.yaml up -d
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
python scripts/gen_dev_keys.py   # paste PEMs into .env JWT_* variables
alembic upgrade head
uvicorn schoolpass.api.main:app --reload --port 8000
# optional: python -m schoolpass.worker.main
pytest
```

Runtime DB role is `schoolpass_app` (**NOBYPASSRLS**). Migrations use `schoolpass_migrator`. See [docs/phase-1.md](docs/phase-1.md).

## Documentation

| Document | Contents |
| --- | --- |
| [docs/architecture.md](docs/architecture.md) | System, tenancy GUCs, invariants, outbox/Service Bus, files, retention, decision index |
| [docs/database.md](docs/database.md) | ERD, FORCE RLS, student vs card assignment, trips, observations |
| [docs/security.md](docs/security.md) | Auth, RBAC, audit, encryption, compliance |
| [docs/api.md](docs/api.md) | API surfaces, versioning, idempotency, contracts |
| [docs/infrastructure.md](docs/infrastructure.md) | Azure, Terraform, CI/CD, monitoring, DR |
| [docs/testing.md](docs/testing.md) | Test pyramid, RLS and ingest tests, environments |
| [docs/phase-1.md](docs/phase-1.md) | Phase 1 implementation decisions |
| [docs/phase-2.md](docs/phase-2.md) | Phase 2 student/guardian/enrollment domain |
| [docs/rfid.md](docs/rfid.md) | UHF gate readers, ingest, dedup, direction |
| [docs/nfc.md](docs/nfc.md) | HF/NFC scanning, card binding, attendant/teacher flows |
| [docs/gps.md](docs/gps.md) | Bus location, geofences, parent visibility |
| [docs/payments.md](docs/payments.md) | Fees, UPI, Razorpay, webhooks, reconciliation |
| [docs/notifications.md](docs/notifications.md) | Push pipeline, templates, privacy of payloads |
