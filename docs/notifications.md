# Notification architecture

**Status:** Architecture only. FCM is a **delivery channel**. Postgres **inbox** is the durable notification record.

Core attendance/payment transactions **must not** call FCM. They write a transactional **outbox** command only.

---

## End-to-end flow

```
Business transaction (same Postgres commit)
  → outbox notify.send (command_id, tenant_id, user_id, template_key, resource ids)
  → publisher → Azure Service Bus
  → notify worker (idempotent)
      1. Insert/upsert notifications inbox row (durable record, delivery_status=pending)
      2. FCM HTTP v1 (if preference allows OS push)
      3. notification_deliveries row (attempt, provider_message_id, result)
      4. inbox delivery_status = sent | failed | skipped_preference | skipped_no_token
```

If FCM is down: inbox already exists; retries/FCM failure do **not** roll back attendance.

In-app list reads `notifications`, not FCM.

---

## 12. Decision: FCM HTTP v1; one GCP project per environment; three app IDs

Flutter flavors register tokens. WhatsApp/SMS are **later channel adapters** on the same command (`channel` field), not a redesign.

### Why / alternatives / cost

Gate loop ends in a parent message. Azure Notification Hubs is an extra hop for v1. OneSignal puts children’s tokens in another SaaS. SMS-per-gate is noise and cost. FCM is free at pilot volume. Google sees tokens and **minimized** payloads (two-cloud tradeoff).

---

## At-least-once, idempotency, retry, DLQ

| Concern | Rule |
| --- | --- |
| Bus delivery | At-least-once |
| Consumer idempotency | Unique `command_id` on inbox insert; second delivery skips FCM if already `sent` **or** retries FCM only if `failed` and attempt policy allows |
| Duplicate prevention | Debounce **upstream** (attendance) plus unique command_id. Rare double OS notification preferred to lost gate notify |
| Retry | Service Bus retries then DLQ; worker also retries FCM with backoff (e.g. 3×) |
| Dead-letter | Alert; replay after fix; do not auto-drop attendance |
| Delivery status | On inbox + each `notification_deliveries` attempt |

**Do not log notification payloads** (title/body/data). Log `command_id`, `template_key`, `user_id`, `tenant_id`, FCM error **code**.

---

## Preferences and targeting

`notification_preferences`: per user × category (`attendance`, `bus`, `fees`, `school_news`, `ops`). OS push may be off; **inbox still written** unless category is fully disabled (product: disable OS vs disable inbox — **decision: category off skips FCM but still writes inbox for fees/attendance; news may skip both**).

| Event | Recipients |
| --- | --- |
| Child operational | `student_guardians` with notify flags |
| Class announcement | Guardians of enrolled students + division teachers |
| School-wide | Tenant memberships except platform |
| Unmatched card | school_admin, not parent |

Quiet hours: delay FCM, inbox immediate (except critical ops — none in v1 GPS coordinates).

---

## Templates and versioning

Server templates: `template_key` + `template_version` + `locale` (`en-IN` v1). Worker renders. Clients do not author attendance/fee wording.

Data passed to templates: **ids and display tokens** (first name, gate name, time). Worker loads names **after** anonymization checks (`pii_state`); anonymized students produce no parent push.

---

## Payload privacy

OS notification **must not** contain:

- Precise GPS coordinates or polylines
- EPC/UID
- Full student dossiers, other children’s names
- Payment instrument details (amount + “fee received” is enough)

`bus_approaching_stop`: stop **name**, not lat/lon.

---

## Mobile constraints

Android channels: `attendance` high, `news` low. iOS: no silent push every 5s for GPS. Token bound to `user_id` + `device_id`; prune on `UNREGISTERED`; logout revokes.

---

## Observability

Metrics: inbox written, FCM sent/failed, invalid token, time from attendance commit to inbox, time to FCM. SLO product: % of `school_in` with inbox row < 15s; FCM best-effort. Alert on worker lag and DLQ. Sample successful sends in App Insights; **100%** of failures without payload PII.
