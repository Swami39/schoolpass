# Phase 3 — Physical cards and card assignments

## Card identity

```
Student (students.id)
  → CardAssignment
    → PhysicalCard
```

Card UIDs/EPCs are **not** student primary keys. `uid_only` is not presented as cryptographically secure.

## Physical card lifecycle

| From | To |
| --- | --- |
| inventory | active, blocked |
| active | blocked, retired |
| blocked | active, retired |
| retired | _(none)_ |

## Assignment lifecycle

Statuses: `pending`, `active`, `lost`, `blocked`, `expired`, `replaced`, `revoked`.

Active assignment rule (pilot): `status = active AND revoked_at IS NULL AND activated_at IS NOT NULL`.

Partial unique indexes enforce:

- one active assignment per student per tenant
- one active assignment per physical card per tenant

## Replacement

Old assignment → `replaced` with `replaced_by_assignment_id` pointing at the new assignment. History is never rewritten.

## Identifier normalization

- HF UID: trim whitespace
- UHF EPC/TID: trim + uppercase

Documented in code (`cards/normalize.py`); no reader-specific decoding.

## Permissions

See migration `0003_card_domain` and `rbac/catalog.py`.

## Outbox (IDs only)

`card.created`, `card.updated`, `card.blocked`, `card.retired`, `card_assignment.*` events with `card_id`, `assignment_id`, `student_id` only.

## Unresolved hardware questions

Exact mandatory identifier combinations per vendor SKU and DESFire field layout remain future work; schema keeps nullable identifiers and extensible `profile`.
