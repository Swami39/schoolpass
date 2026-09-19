# Phase 2 implementation notes

Student, guardian, enrollment, and academic structure domain. Phase 1 foundations unchanged.

## Tables (FORCE RLS, `tenant_id` NOT NULL)

- `files` — minimal metadata for `photo_file_id` (no blob upload in this phase)
- `academic_years`, `classes`, `sections`
- `students` — `historical_subject_id` (global unique), tenant-scoped `admission_no`, `pii_state`, `status`
- `guardians` — tenant-scoped contacts (no global person identity)
- `student_guardians` — M:N with notify/fee flags
- `enrollments` — historical placement; partial unique index enforces one active open enrollment per student per tenant

## Cross-tenant integrity

Composite foreign keys tie `(child_id, tenant_id)` to parent `(id, tenant_id)` on students, guardians, classes, sections, academic years, and photo files.

## Permissions (seeded in migration `0002_student_domain`)

`students:*`, `guardians:*`, `student_guardians:*`, `enrollments:*`, `academic:*`, `files:*` — assigned per role in migration and `rbac/catalog.py`.

## Outbox topics (identifier payloads only)

`student.created`, `student.updated`, `student.withdrawn`, `student.anonymized`, `enrollment.created`

## API surface

Under `/api/v1`: students CRUD/lifecycle, guardians, student-guardian links, enrollments, minimal academic structure POSTs. Tenant from JWT only.

## Tests

`tests/test_students_domain.py` plus existing Phase 1 suite (28 tests total).
