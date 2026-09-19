import 'dart:async';

import 'gps_models.dart';
import 'gps_outbox_store.dart';
import 'gps_sync_client.dart';
import 'models.dart';
import 'sync_client.dart';
import 'sync_worker.dart';

class GpsSyncWorker {
  GpsSyncWorker({
    required this.store,
    required this.client,
    required this.clientDeviceId,
    this.config = const SyncWorkerConfig(),
    this.maxBatchSize = kGpsMaxBatchSize,
    DateTime Function()? clock,
  }) : _clock = clock ?? DateTime.now;

  final GpsOutboxStore store;
  final TransportGpsSyncClient client;
  final String clientDeviceId;
  final SyncWorkerConfig config;
  final int maxBatchSize;
  final DateTime Function() _clock;

  static Future<void>? _coalescedDrain;
  bool _loopActive = false;

  void recoverOnStartup() => store.recoverSyncingToPending();

  Future<void> drainPending() async {
    while (_coalescedDrain != null) {
      await _coalescedDrain;
    }
    if (_loopActive) {
      return;
    }
    _loopActive = true;
    final completer = Completer<void>();
    _coalescedDrain = completer.future;
    try {
      while (true) {
        final batch = store.claimPendingBatch(limit: maxBatchSize);
        if (batch.isEmpty) {
          break;
        }
        final transient = await _syncBatch(batch);
        if (transient) {
          break;
        }
      }
    } finally {
      _loopActive = false;
      _coalescedDrain = null;
      completer.complete();
    }
  }

  Future<bool> _syncBatch(List<GpsOutboxSample> batch) async {
    final now = _clock();
    final ids = [for (final s in batch) s.localId];
    store.markBatchAttemptStarted(ids, now);
    final requests = [
      for (final s in batch)
        TransportGpsSampleRequest(
          clientSampleId: s.clientSampleId,
          tripId: s.tripId,
          latitude: s.latitude,
          longitude: s.longitude,
          occurredAt: s.occurredAt,
          deviceSequence: s.deviceSequence,
          accuracyMeters: s.accuracyMeters,
          altitudeMeters: s.altitudeMeters,
          speedMps: s.speedMps,
          headingDegrees: s.headingDegrees,
        ),
    ];
    try {
      final results = await client.syncBatch(
        samples: requests,
        clientDeviceId: clientDeviceId,
      );
      final ackAt = _clock();
      for (var i = 0; i < batch.length; i++) {
        final sample = batch[i];
        final result = i < results.length ? results[i] : null;
        if (result == null) {
          store.returnBatchToPending([sample.localId], lastError: 'missing_result');
          continue;
        }
        final terminal = _terminalState(result.result);
        store.applyResult(
          localId: sample.localId,
          terminalState: terminal,
          response: result,
          acknowledgedAt: ackAt,
        );
      }
      return false;
    } on SyncAuthConfigurationFailure catch (e) {
      store.markBatchRejectedFromHttp(ids, 'auth_${e.statusCode}', _clock());
      return false;
    } on SyncPermanentHttpFailure catch (e) {
      store.markBatchRejectedFromHttp(ids, 'http_${e.statusCode}', _clock());
      return false;
    } on SyncTransientFailure catch (e) {
      store.returnBatchToPending(ids, lastError: e.message);
      return true;
    } catch (e) {
      store.returnBatchToPending(ids, lastError: e.toString());
      return true;
    }
  }

  OutboxSyncState _terminalState(String result) {
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
