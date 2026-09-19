# Fee management and UPI payments

**Status:** Architecture only. Client “payment success” is **never** authoritative. Only verified server-side provider events (or audited office cash) change ledger state.

India-first: **UPI** as the primary method via a PSP adapter. Cards/netbanking only if the same checkout supports them.

---

## Two rails (do not mix)

| Rail | Payer | Payee | Ledger | PSP credentials |
| --- | --- | --- | --- | --- |
| **A. School fees** | Parent (guardian with `can_pay_fees`) | **School (merchant)** | Tenant `invoices` / `payments` | Per-school, Key Vault |
| **B. SaaS subscription** | School | **SchoolPass** | `platform_subscriptions` / `platform_payments` | Platform merchant account |

Do not settle school fees through the platform Razorpay account. Do not mark SaaS paid from a parent fee webhook.

---

## 13. Decision: provider adapter + Razorpay as first adapter; webhooks own state

```
Parent ─► API create payment_attempt + provider order (adapter)
       ─► Official checkout / UPI
Provider ─► POST /hooks/v1/{provider} 
       ─► verify signature 
       ─► persist payment_webhooks (unique provider_event_id)
       ─► outbox payments.webhook (id only)
       ─► worker: adapter maps event → ledger transition
       ─► inbox notify (payment_captured)
```

SchoolPass tables are the **school-facing ledger**. The PSP is the cash register. Daily **reconciliation** job compares them.

### Adapter

`PaymentProvider` port: `create_order`, `parse_and_verify_webhook`, `fetch_payment` (reconciliation), `initiate_refund`. Razorpay is the first implementation. Cashfree/PayU can be added **without rewriting** invoice state machines. `payments.provider` stores the adapter key.

### Why / alternatives / cost

UPI is expected. Stripe is weak for UPI. Direct NPCI is not our license. MDR is the school’s (rail A). Do not log full webhook payloads.

---

## External validation prerequisite (production blocker for rail A)

The **multi-school merchant, KYC, settlement, and commercial model is not confirmed** by this document.

Architecture **assumes until validated**: each school is the merchant (Razorpay Route / sub-merchant / school’s own account). SchoolPass stores per-tenant credentials and is **not** an unlicensed aggregator.

If Razorpay onboarding cannot support that model:

- **Do not ship parent fee collection** on a pooled SchoolPass account.
- Options after legal/PSP confirmation: pause rail A; or a licensed aggregator model (product + legal change).

This is an **external prerequisite**, not an application TBD.

---

## Order and attempt lifecycle (rail A)

1. Invoice `issued` (server totals). Client amount **ignored**.
2. `POST /fees/invoices/{id}/pay` + `Idempotency-Key` → `payment_attempts` `created` + provider `order_id`. Replay returns the same order.
3. Parent completes UPI. Client may show pending UI. **Ledger stays pending.**
4. Webhook: signature verified with **that tenant’s** (or platform’s) secret as applicable.
5. Duplicate `provider_event_id`: persist skip, HTTP 200.
6. Worker transitions attempt `captured` / `failed`; invoice `paid` / stays issued. Settlement/reference ids stored (`provider_payment_id`, `settlement_id` if provided).
7. Refunds: school_finance or PSP dashboard + `refunds` row; parent cannot self-refund. Adapter `initiate_refund` optional in v1 (manual PSP + reconcile).
8. Expire job 30–45 min: attempt `expired`; parent new attempt.

Offline office cash: `provider=offline_cash`, actor `school_finance`, **audited**. Not a fake UPI.

---

## Webhook processing rules

- TLS endpoint `hooks.schoolpass.example`.
- Verify signature **before** any state change.
- Store raw body **encrypted at rest** in `payment_webhooks` for dispute (FINANCIAL). **Do not** copy the body to App Insights.
- Idempotency: unique `provider` + `provider_event_id`.
- Unknown invoice/order: retry via outbox; do not create a paid invoice from thin air.
- Rail selection: webhook routing by path/credential (`/hooks/v1/razorpay/platform` vs `/hooks/v1/razorpay/tenant/{tenant}` or account id in payload **after** verify). Tenant still from **our** order row, not from a client.

---

## Reconciliation and audit

Daily job: fetch provider settlements vs `payments` in `captured`. Exceptions queue for finance. Audit: attempt created, captured, failed, refunded, invoice void — actor or `actor_type=system`/`device` N/A, webhooks are `actor_type=system` with `provider` in metadata.

---

## Failure modes

| Event | Behavior |
| --- | --- |
| User kills UPI app | pending until webhook or expire |
| Webhook before our commit | store webhook; retry match |
| Double webhook | unique constraint; 200 |
| Client posts `payment_id` as paid | **ignored** as authority; may trigger *fetch* for UX, still verify |
| Razorpay outage | invoices remain issued |

---

## Test vs live

Staging: Razorpay **test** keys, real signature verification, documented test payloads. Production: live keys. Environment selects credentials only — **no** `if pay_test then mark paid` in shared domain code.

Deterministic tests: fixture signatures ([testing.md](testing.md)). No real money in CI.

---

## Platform subscriptions (rail B)

Annual plan via **platform** merchant credentials. Webhook refreshes `platform_subscriptions` and entitlements.

Lapse policy: `grace` then `suspended`. **Attendance ingest stays up during grace** so a billing dispute does not brick the gate. Super-admin may disable a tenant explicitly. Parent fee pay (rail A) is independent of rail B except when the whole tenant is disabled.

---

## Security

Parents pay only their children’s invoices. RLS on invoices/payments. Key rotation in Key Vault. No PAN/VPA storage beyond provider tokens/ids.
