import 'package:uuid/uuid.dart';

import 'gps_models.dart';
import 'gps_outbox_store.dart';
import 'gps_sampling_policy.dart';
import 'gps_sync_worker.dart';
import 'trip_context.dart';

const _uuid = Uuid();

class GpsSampleService {
  GpsSampleService({
    required this.store,
    required this.tripContext,
    required this.clientDeviceId,
    required this.syncWorker,
    this.policy = GpsSamplingPolicy.defaultPolicy,
    DateTime Function()? clock,
  }) : _clock = clock ?? DateTime.now;

  final GpsOutboxStore store;
  final TripContext tripContext;
  final String clientDeviceId;
  final GpsSyncWorker syncWorker;
  final GpsSamplingPolicy policy;
  final DateTime Function() _clock;

  DateTime? _lastCapturedAt;
  double? _lastLat;
  double? _lastLon;

  GpsOutboxSample capturePosition(GpsPosition position) {
    final trip = tripContext.currentTrip;
    if (trip == null) {
      throw NoActiveTripForGpsError();
    }
    final now = _clock();
    if (!policy.shouldCapture(
      now: now,
      lastCapturedAt: _lastCapturedAt,
      lastLatitude: _lastLat,
      lastLongitude: _lastLon,
      latitude: position.latitude,
      longitude: position.longitude,
      accuracyMeters: position.accuracyMeters,
    )) {
      throw StateError('sample suppressed by policy');
    }
    final clientSampleId = _uuid.v4();
    final deviceSequence = store.nextDeviceSequence();
    final row = store.insertPending(
      clientSampleId: clientSampleId,
      clientDeviceId: clientDeviceId,
      tripId: trip.tripId,
      latitude: position.latitude,
      longitude: position.longitude,
      occurredAt: position.occurredAt,
      localCreatedAt: now,
      deviceSequence: deviceSequence,
      accuracyMeters: position.accuracyMeters,
      altitudeMeters: position.altitudeMeters,
      speedMps: position.speedMps,
      headingDegrees: position.headingDegrees,
    );
    _lastCapturedAt = now;
    _lastLat = position.latitude;
    _lastLon = position.longitude;
    return row;
  }

  Future<void> captureAndTrySync(GpsPosition position) async {
    final sample = capturePosition(position);
    syncWorker.recoverOnStartup();
    await syncWorker.drainPending();
    store.getByClientSampleId(sample.clientSampleId);
  }
}
