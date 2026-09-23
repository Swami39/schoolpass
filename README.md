# SchoolPass

Production SaaS for schools: dual-frequency (HF + UHF) student cards, gate attendance, bus boarding with offline sync, GPS, parent communication, academics, and UPI fees.

**Phase 1** is the backend foundation (FastAPI, PostgreSQL RLS, auth, audit, outbox). **Phase 2** adds students, guardians, enrollments, and academic structure. **Phase 3** adds physical cards and card assignments. Product domains (RFID ingest, NFC, GPS, fees, apps) are not implemented yet.

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

## Run the whole stack with Docker (Android phones on the same Wi-Fi)

```bash
cp .env.example .env
python scripts/gen_dev_keys.py   # paste PEMs into the .env JWT_* variables
docker compose -f infra/docker/compose.yaml up -d --build
docker compose -f infra/docker/compose.yaml exec api python scripts/seed_local_demo.py
```

This starts PostgreSQL, Redis, the API, and the background worker.
Migrations run automatically when the API container starts, and the API
listens on `0.0.0.0:8000` so phones on the LAN can reach it.

Then point the phone apps at this Mac and install them:

```bash
./scripts/build_android_physical_apks.sh   # auto-detects this Mac's LAN IP
# install dist/android-apks/*.apk on the Android devices (same Wi-Fi)
```

Demo logins are written to `.data/local_demo_credentials.json`
(password `Demo-Local-Only-2026`). If this Mac's Wi-Fi IP changes, rebuild
the APKs — the API address is baked in at build time.

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
| [docs/phase-3.md](docs/phase-3.md) | Phase 3 physical cards and assignments |
| [docs/rfid.md](docs/rfid.md) | UHF gate readers, ingest, dedup, direction |
| [docs/rfid-srk6gwl.md](docs/rfid-srk6gwl.md) | SRK-6GWL reader integration: edge agent, provisioning, operations |
| [docs/nfc.md](docs/nfc.md) | HF/NFC scanning, card binding, attendant/teacher flows |
| [docs/gps.md](docs/gps.md) | Bus location, geofences, parent visibility |
| [docs/payments.md](docs/payments.md) | Fees, UPI, Razorpay, webhooks, reconciliation |
| [docs/notifications.md](docs/notifications.md) | Push pipeline, templates, privacy of payloads |
