import 'dart:io';

import 'package:attendant_nfc/attendant_nfc.dart';
import 'package:test/test.dart';

void main() {
  group('Teacher class NFC outbox', () {
    late Directory tempDir;
    late String dbPath;

    setUp(() {
      tempDir = Directory.systemTemp.createTempSync('teacher_nfc_test_');
      dbPath = '${tempDir.path}/outbox.db';
    });

    tearDown(() {
      tempDir.deleteSync(recursive: true);
    });

    TeacherClassNfcOutboxStore reopenStore() => TeacherClassNfcOutboxStore.open(path: dbPath);

    test('offline scan persists with stable client_event_id', () {
      final store = reopenStore();
      final section = SectionContext()..setSection('section-a');
      final client = FakeTeacherClassNfcSyncClient();
      final worker = TeacherClassNfcSyncWorker(
        store: store,
        client: client,
        clientDeviceId: 'device-1',
      );
      final service = TeacherClassNfcEventService(
        store: store,
        sectionContext: section,
        clientDeviceId: 'device-1',
        syncWorker: worker,
      );
      final event = service.recordScan(cardUid: '04abc');
      expect(event.syncState, OutboxSyncState.pending);
      store.close();
      final store2 = reopenStore();
      final loaded = store2.getByLocalId(event.localId);
      expect(loaded?.clientEventId, event.clientEventId);
      store2.close();
    });

    test('recover syncing to pending on startup', () {
      final store = reopenStore();
      store.insertPendingEvent(
        clientEventId: 'evt-1',
        clientDeviceId: 'device-1',
        sectionId: 'section-a',
        cardUid: 'uid',
        occurredAt: DateTime.now().toUtc(),
        deviceSequence: 1,
        createdAt: DateTime.now().toUtc(),
      );
      expect(store.claimNextPending(), isNotNull);
      store.close();
      final store2 = reopenStore();
      expect(store2.recoverSyncingToPending(), 1);
      store2.close();
    });
  });
}
