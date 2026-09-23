# Attendant NFC (Phase 6B.3)

Dart package for **durable NFC outbox + offline sync** against the existing SchoolPass API:

`POST /api/v1/transport/nfc/events/sync` with header `X-Client-Device-Id`.

## Integration boundary

| Layer | Responsibility |
| --- | --- |
| **Platform NFC plugin** (Flutter, not in this package) | Read raw UID from OS |
| [`NfcAdapter`](lib/src/nfc_adapter.dart) | Stream of normalized scans |
| [`NfcEventService`](lib/src/event_service.dart) | Trip context, sequence, outbox insert |
| [`NfcOutboxStore`](lib/src/outbox_store.dart) | SQLite persistence |
| [`NfcSyncWorker`](lib/src/sync_worker.dart) | Ordered sync, crash recovery |
| **App auth layer** (existing) | JWT + registered `client_device_id`; wire [`TransportNfcSyncClient`](lib/src/sync_client.dart) to your HTTP stack |

Do **not** put tokens or `tenant_id` in outbox rows or sync JSON bodies.

## Local development

```bash
cd apps/mobile/attendant_nfc
dart pub get
dart test
dart analyze
```

On device, open the store with a file path under app support (SQLCipher optional per [security.md](../../../docs/security.md)).

## Flutter app

Production shell: `apps/mobile/attendant_app_mobile` (uses this package). Import from other apps only if you need a custom flavor:


1. Register `client_device_id` via existing identity APIs.
2. Provide [`MutableTripContext`](lib/src/trip_context.dart) from the active trip UI/state.
3. Implement `TransportNfcSyncClient` using the authenticated HTTP client (Bearer JWT).
4. Wrap the platform NFC plugin in `NfcAdapter`.

See [docs/mobile-nfc-outbox.md](../../../docs/mobile-nfc-outbox.md).
