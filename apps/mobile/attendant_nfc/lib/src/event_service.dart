import 'package:uuid/uuid.dart';

import 'models.dart';
import 'nfc_adapter.dart';
import 'outbox_store.dart';
import 'sync_worker.dart';
import 'trip_context.dart';

const _uuid = Uuid();

/// Captures NFC scans into the durable outbox (offline-first).
class NfcEventService {
  NfcEventService({
    required this.store,
    required this.tripContext,
    required this.clientDeviceId,
    required this.syncWorker,
    DateTime Function()? clock,
  }) : _clock = clock ?? DateTime.now;

  final NfcOutboxStore store;
  final TripContext tripContext;
  final String clientDeviceId;
  final NfcSyncWorker syncWorker;
  final DateTime Function() _clock;

  NfcOutboxEvent recordScan({
    required String cardUid,
    required NfcEventType eventType,
  }) {
    final trip = tripContext.currentTrip;
    if (trip == null) {
      throw NoActiveTripError();
    }
    final clientEventId = _uuid.v4();
    final occurredAt = _clock();
    final createdAt = _clock();
    final deviceSequence = store.nextDeviceSequence();
    return store.insertPendingEvent(
      clientEventId: clientEventId,
      clientDeviceId: clientDeviceId,
      eventType: eventType,
      cardUid: cardUid,
      tripId: trip.tripId,
      tripStopId: trip.tripStopId,
      occurredAt: occurredAt,
      deviceSequence: deviceSequence,
      createdAt: createdAt,
    );
  }

  Future<NfcOutboxEvent> recordScanAndTrySync({
    required String cardUid,
    required NfcEventType eventType,
    bool Function()? isNetworkAvailable,
  }) async {
    final event = recordScan(cardUid: cardUid, eventType: eventType);
    final online = isNetworkAvailable?.call() ?? true;
    if (online) {
      syncWorker.recoverOnStartup();
      await syncWorker.drainPending();
    }
    return store.getByLocalId(event.localId) ?? event;
  }

  Future<void> handleNfcScan(NfcScanResult scan, NfcEventType eventType) async {
    await recordScanAndTrySync(cardUid: scan.cardUid, eventType: eventType);
  }
}
