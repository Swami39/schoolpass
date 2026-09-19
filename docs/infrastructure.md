# Infrastructure architecture

**Status:** Architecture only. No Terraform applied in this phase.

Azure, Terraform, Docker, GitHub Actions, monitoring, disaster recovery, environments.

---

## 22. Azure architecture

### Choice

**Single region for pilot (Central India or South India), hub-and-spoke optional later.** Prefer **Azure Container Apps** (or App Service for API if Container Apps cold-start policy is unacceptable) + **Azure Database for PostgreSQL Flexible Server** + **Azure Cache for Redis** + **Service Bus** + **Blob** + **Key Vault** + **Front Door** + **Azure Monitor**.

```
Internet → Front Door (WAF) ┬→ Container Apps: api (public)
                            ├→ Container Apps: ingest (optional separate app)
                            └→ Static Web Apps / App Service: Next.js (or Front Door → web)

Container Apps: worker (min replicas 1 during school hours)
Flexible Server (private endpoint) ← api/worker via VNet integration
Redis (private)
Service Bus (RBAC)
Blob + Key Vault
GitHub Actions OIDC → ACR, Terraform state in Blob
```

**DNS:** `app` (parent web if any), `admin`, `platform`, `api`, `ingest`.

**Identity:** Azure AD for **operators**; application users are first-party ([security.md](security.md)).

### Why it is needed

The technology direction is Azure. Children’s data should not sprawl across unsanctioned clouds. Private endpoints keep Postgres off the public internet.

### Alternatives considered

| Alternative | Tradeoff |
| --- | --- |
| AKS | Correct at large scale; expensive and skilled-ops heavy for 1–10 schools. Container Apps first; AKS when we need sidecars/mesh. |
| Functions-only | RFID burst + RLS session setup is a poor fit for the API. Functions OK for schedulers. |
| AWS / GCP | Not the stated direction unless a later review shows India region or cost issues. |
| VMs + docker-compose | Faster first deploy, worse patching and identity. |

### Tradeoffs

Container Apps scale-to-zero on **workers** would delay morning notifications. **Min replicas ≥ 1** on `worker` 05:00–18:00 local, scale-to-zero overnight if we accept slow first push.

Next.js: **separate** from Python. Host on Azure Static Web Apps + API, or Container Apps. SSR for admin is useful for auth cookies; if cookies are on `api` domain, SPA + Front Door is enough.

### Scalability

Scale-out API on CPU/RPS. Postgres: start GP 2–4 vCore; enable read replica when parent polling hurts writes. Redis for last GPS point so Postgres is not on the 2s poll path.

Thousands of schools: second region is **DR first**, then active ingest in the region of the school (`data_residency`).

### Security

- Public network access **disabled** on Flexible Server.
- Key Vault purge protection in prod.
- ACR with private link or at least admin disabled + RBAC.
- Front Door WAF in prevention mode after a week of detection.

### Cost (order of magnitude, pilot)

Dominant: Flexible Server, Front Door, Monitor ingestion. Keep sample GPS out of App Insights. Use resource tags `env`, `service`. Budget alerts from day one.

---

## Terraform

- `infra/terraform/modules/*` reusable.
- State: Azure Blob + lease, one state per env (`staging`, `prod`).
- `local` uses Docker Compose for Postgres/Redis/Service Bus emulator if available; Terraform not required for laptops.
- No manual portal resources in prod. Drift = bug.

---

## 21. CI/CD architecture

### Choice

**GitHub Actions** with OIDC to Azure (no long-lived SP secrets in GitHub if avoidable).

Pipelines:

1. **CI (all PRs):** lint, unit, `pytest` with Postgres service, RLS tests, OpenAPI diff, Flutter analyze, Next.js typecheck. Build images, do not push to prod ACR tags.
2. **Staging deploy (main):** Terraform plan (and apply with environment protection), migrate Alembic, deploy containers, smoke tests (auth + health, **not** against real children).
3. **Production:** same with **required reviewer**, backup snapshot tag, migrate, deploy, smoke.

Images: tagged by git SHA. Prod deploy by SHA, not `latest`.

Mobile: Flutter build on tags; store submit is **manual** in v1 (review cycles). Internal test tracks automated.

### Why it is needed

A SaaS that takes fees and attendance cannot be FTP’d from a laptop.

### Alternatives

Azure DevOps, GitLab. GitHub is the stated direction. CircleCI adds another vendor.

### Tradeoffs

OIDC setup is fiddly once, then safer. Long Actions minutes on Flutter; cache Gradle/CocoaPods; only run iOS on tags if cost hurts.

### Scale / security / cost

Path filters. Fork PRs do not get Azure credentials. Cost: Actions + ACR storage. Security: production environment in GitHub with wait timer optional.

---

## 18. Logging and monitoring

### Choice

**OpenTelemetry SDK** in API and workers → **Azure Monitor / Application Insights**. Structured **JSON logs** (stdout) with `correlation_id` / `request_id`, `tenant_id`, `actor_type`, `user_id` when present.

**Do not log:** student dossiers, payment/webhook payloads, notification payloads, secrets, tokens, GPS streams (default). See [security.md](security.md).

**Azure Service Bus:** Standard for pilot; **workload identity** (no prod SAS in app settings when feasible). Message ids, correlation ids, tenant ids, idempotency keys, schema_version; payload = identifiers. Retry then DLQ; alert on DLQ. GPS samples are **not** bus messages ([architecture.md](architecture.md) §15).

Metrics: ingest accepted/rejected, attendance debounce drops, sync lag (`received_at − occurred_at`), FCM failure, payment webhook age, bus last-seen age, reader last-seen, worker tenant-mismatch, DLQ depth.

Alerts (prod):

- Ingest 5xx > threshold for 5 min.
- Reader silent during school hours (per reader `last_seen`).
- Worker lag / DLQ depth.
- Postgres storage > 80%.
- Failed payment webhooks.
- TLS/cert expiry.

Uptime: Front Door health probes on `/health/live` (process) and `/health/ready` (Postgres ping). Ingest has its own probes.

**Sentry** optional for Flutter and Next.js; disable PII (no form payloads). If Sentry is used, DPA required.

### Why needed

Bell-time failures are silent if we only look at CPU. Reader liveness is a **product** signal (school thinks the gate “missed” a child).

### Alternatives

ELK self-host (ops cost), Grafana Cloud (another vendor). Azure Monitor is enough if we **filter** high-cardinality GPS.

### Tradeoffs

App Insights can get expensive. Sample 10% of successful parent GETs; **100% of ingest errors and payment paths**.

### Security

Logs may contain tenant UUIDs and student UUIDs. Restrict Monitor access. **No student names, coordinates, or payment bodies** at info/default.

---

## 20. Disaster recovery

| Target (pilot) | Value |
| --- | --- |
| RPO | 1 hour (Flexible Server backups typically better; *declare* 1h) |
| RTO | 4 hours |
| Region | Single region + geo-redundant backups |
| Later (paid HA) | RPO 15 min, RTO 1 h, warm replica in paired region |

**Backups:** Flexible Server PITR enabled; Blob RA-GRS for receipts and photos; Terraform state geo-redundant. Weekly **restore test** to a scratch server in staging subscription (prove backups, do not restore over prod).

**Failure modes:**

- Region outage: restore Postgres to paired region, re-point DNS, accept GPS/ingest downtime during RTO. Attendant **offline queue still works**; sync when API returns.
- Ransomware / bad migration: PITR + immutable blob for audit.
- Razorpay outage: invoices stay open; no client-side “mark paid”.
- FCM outage: persist `notify.send`; retry; attendance still recorded.

**Runbooks** (to be written at implementation): reader credential rotation, tenant disable, stolen attendant phone, webhook replay.

### Alternatives

Active-active two regions: double cost, session and bus ordering complexity. Not for 1–10 schools.

### Cost

Geo backups are cheap vs a second live stack. Do not buy AKS multi-region until RTO contracts demand it.

---

## 23. Environments (infra view)

| Env | Azure subscription | Notes |
| --- | --- | --- |
| local | none | Compose: Postgres 16, Redis, Azurite, optionally Service Bus emulator |
| ci | none | GitHub service containers |
| staging | `schoolpass-nonprod` | Smaller SKUs, Razorpay test keys |
| production | `schoolpass-prod` | Separate subscription so billing and IAM cannot cross |

Developers are not Contributors on prod. Platform super-admin **application** role ≠ Azure Owner.

---

## Networking sketch

- VNet: `snet-ca`, `snet-db`, `snet-privatelink`.
- Outbound: FCM, Razorpay, SMS. Explicit FQDN allowlist if using firewall.
- Ingest: may need to accept many school NATs; do not require site-to-site VPN in v1 (schools will not buy it). Device auth instead. Optional VPN for a large trust’s on-prem edge agent later.

---

## Containers

- Distroless or slim Python images, non-root.
- API and worker same image, different command (reduces drift).
- Read-only root FS where possible.
- Secrets from Key Vault refs, not baked in.
