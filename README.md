# SchoolPass

Production SaaS for schools: dual-frequency (HF + UHF) student cards, gate attendance, bus boarding with offline sync, GPS, parent communication, academics, and UPI fees.

This repository currently contains **architecture only**. Application code, APIs, and UI are not implemented yet.

## Documentation

| Document | Contents |
| --- | --- |
| [docs/architecture.md](docs/architecture.md) | System, tenancy GUCs, invariants, outbox/Service Bus, files, retention, decision index |
| [docs/database.md](docs/database.md) | ERD, FORCE RLS, student vs card assignment, trips, observations |
| [docs/security.md](docs/security.md) | Auth, RBAC, audit, encryption, compliance |
| [docs/api.md](docs/api.md) | API surfaces, versioning, idempotency, contracts |
| [docs/infrastructure.md](docs/infrastructure.md) | Azure, Terraform, CI/CD, monitoring, DR |
| [docs/testing.md](docs/testing.md) | Test pyramid, RLS and ingest tests, environments |
| [docs/rfid.md](docs/rfid.md) | UHF gate readers, ingest, dedup, direction |
| [docs/nfc.md](docs/nfc.md) | HF/NFC scanning, card binding, attendant/teacher flows |
| [docs/gps.md](docs/gps.md) | Bus location, geofences, parent visibility |
| [docs/payments.md](docs/payments.md) | Fees, UPI, Razorpay, webhooks, reconciliation |
| [docs/notifications.md](docs/notifications.md) | Push pipeline, templates, privacy of payloads |

## Status

Architecture phase. Do not treat missing application code as implied mocks; implementation starts only after this design is accepted.
