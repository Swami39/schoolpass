import 'dart:async';

import 'models.dart';
import 'sync_client.dart';
import 'sync_worker.dart' show SyncWorkerConfig;
import 'teacher_models.dart';
import 'teacher_outbox_store.dart';
import 'teacher_sync_client.dart';

class TeacherClassNfcSyncWorker {
  TeacherClassNfcSyncWorker({
    required this.store,
    required this.client,
    required this.clientDeviceId,
    this.config = const SyncWorkerConfig(),
    DateTime Function()? clock,
  }) : _clock = clock ?? DateTime.now;

  final TeacherClassNfcOutboxStore store;
  final TeacherClassNfcSyncClient client;
  final String clientDeviceId;
  final SyncWorkerConfig config;
  final DateTime Function() _clock;

  bool _loopActive = false;
  static Future<void>? _coalescedDrain;

  void recoverOnStartup() {
    store.recoverSyncingToPending();
  }

  Future<void> drainPending() async {
    while (_coalescedDrain != null) {
      await _coalescedDrain;
    }
    if (_loopActive) return;
    _loopActive = true;
    final completer = Completer<void>();
    _coalescedDrain = completer.future;
    try {
      while (true) {
        final claimed = store.claimNextPending();
        if (claimed == null) break;
        final transient = await _syncOne(claimed);
        if (transient) break;
      }
    } finally {
      _loopActive = false;
      _coalescedDrain = null;
      completer.complete();
    }
  }

  Future<bool> _syncOne(TeacherClassNfcOutboxEvent event) async {
    final now = _clock();
    store.markSyncAttemptStarted(event.localId, now);
    final request = TeacherClassNfcSyncRequest(
      clientEventId: event.clientEventId,
      sectionId: event.sectionId,
      cardUid: event.cardUid,
      occurredAt: event.occurredAt,
      deviceSequence: event.deviceSequence,
    );
    try {
      final response = await client.syncEvent(
        request: request,
        clientDeviceId: clientDeviceId,
      );
      final ackAt = _clock();
      final terminal = _terminalStateForResult(response.result);
      store.applyServerAcknowledgement(
        localId: event.localId,
        terminalState: terminal,
        response: response,
        acknowledgedAt: ackAt,
      );
      return false;
    } on SyncAuthConfigurationFailure catch (e) {
      store.markRejectedFromClientHttp(
        localId: event.localId,
        lastError: 'auth_${e.statusCode}',
        acknowledgedAt: _clock(),
      );
      return false;
    } on SyncPermanentHttpFailure catch (e) {
      store.markRejectedFromClientHttp(
        localId: event.localId,
        lastError: 'http_${e.statusCode}',
        acknowledgedAt: _clock(),
      );
      return false;
    } on SyncTransientFailure catch (e) {
      final updated = store.getByLocalId(event.localId);
      if (updated != null && updated.attemptCount >= config.maxTransientAttempts) {
        store.markRejectedFromClientHttp(
          localId: event.localId,
          lastError: 'transient_exhausted',
          acknowledgedAt: _clock(),
        );
        return false;
      }
      store.returnToPending(event.localId, lastError: e.message);
      return true;
    } catch (e) {
      store.returnToPending(event.localId, lastError: e.toString());
      return true;
    }
  }

  OutboxSyncState _terminalStateForResult(String result) {
    switch (result) {
      case 'processed':
        return OutboxSyncState.processed;
      case 'duplicate':
        return OutboxSyncState.duplicate;
      case 'rejected':
        return OutboxSyncState.rejected;
      default:
        throw SyncTransientFailure('unexpected result: $result');
    }
  }
}
