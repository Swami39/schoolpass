import 'package:uuid/uuid.dart';

import 'section_context.dart';
import 'teacher_models.dart';
import 'teacher_outbox_store.dart';
import 'teacher_sync_worker.dart';

const _uuid = Uuid();

class TeacherClassNfcEventService {
  TeacherClassNfcEventService({
    required this.store,
    required this.sectionContext,
    required this.clientDeviceId,
    required this.syncWorker,
    DateTime Function()? clock,
  }) : _clock = clock ?? DateTime.now;

  final TeacherClassNfcOutboxStore store;
  final SectionContext sectionContext;
  final String clientDeviceId;
  final TeacherClassNfcSyncWorker syncWorker;
  final DateTime Function() _clock;

  TeacherClassNfcOutboxEvent recordScan({required String cardUid}) {
    final sectionId = sectionContext.currentSectionId;
    if (sectionId == null) {
      throw NoActiveSectionError();
    }
    final clientEventId = _uuid.v4();
    final occurredAt = _clock();
    final createdAt = _clock();
    final deviceSequence = store.nextDeviceSequence();
    return store.insertPendingEvent(
      clientEventId: clientEventId,
      clientDeviceId: clientDeviceId,
      sectionId: sectionId,
      cardUid: cardUid,
      occurredAt: occurredAt,
      deviceSequence: deviceSequence,
      createdAt: createdAt,
    );
  }

  Future<TeacherClassNfcOutboxEvent> recordScanAndTrySync({
    required String cardUid,
    bool Function()? isNetworkAvailable,
  }) async {
    final event = recordScan(cardUid: cardUid);
    final online = isNetworkAvailable?.call() ?? true;
    if (online) {
      syncWorker.recoverOnStartup();
      await syncWorker.drainPending();
    }
    return store.getByLocalId(event.localId) ?? event;
  }
}
