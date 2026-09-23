import 'dart:async';

import 'package:flutter/foundation.dart';
import 'package:geolocator/geolocator.dart';

import '../auth/auth_models.dart';
import 'gps_models.dart';
import 'gps_sync_client.dart';

enum GpsTrackerPhase {
  starting,
  tracking,
  permissionDenied,
  serviceDisabled,
  error,
  stopped,
}

/// Point-in-time view of the tracker for the UI.
class GpsTrackerSnapshot {
  const GpsTrackerSnapshot({
    required this.phase,
    required this.pendingCount,
    required this.syncedCount,
    this.lastFixAt,
    this.message,
  });

  final GpsTrackerPhase phase;
  final int pendingCount;
  final int syncedCount;
  final DateTime? lastFixAt;
  final String? message;

  GpsTrackerSnapshot copyWith({
    GpsTrackerPhase? phase,
    int? pendingCount,
    int? syncedCount,
    DateTime? lastFixAt,
    String? message,
  }) {
    return GpsTrackerSnapshot(
      phase: phase ?? this.phase,
      pendingCount: pendingCount ?? this.pendingCount,
      syncedCount: syncedCount ?? this.syncedCount,
      lastFixAt: lastFixAt ?? this.lastFixAt,
      message: message,
    );
  }
}

/// Collects GNSS fixes for one trip and syncs them in batches.
///
/// Trip-scoped: construct per trip screen, [stop] when the trip ends or the
/// screen closes. Samples buffer in memory and flush periodically; the server
/// dedupes on `client_sample_id`, so retries are safe. Nothing is written to
/// disk — unsent fixes are dropped when the screen closes, which is fine for
/// live location.
class TripGpsTracker {
  TripGpsTracker({
    required this.tripId,
    required this.clientDeviceId,
    required this.syncClient,
    this.onAuthFailure,
    this.flushInterval = const Duration(seconds: 20),
    this.flushThreshold = 15,
  });

  final String tripId;
  final String clientDeviceId;
  final HttpGpsSyncClient syncClient;
  final void Function()? onAuthFailure;
  final Duration flushInterval;
  final int flushThreshold;

  /// Hard cap so a long offline stretch cannot grow memory unbounded.
  static const int maxBufferedSamples = 300;

  final ValueNotifier<GpsTrackerSnapshot> snapshot = ValueNotifier(
    const GpsTrackerSnapshot(phase: GpsTrackerPhase.starting, pendingCount: 0, syncedCount: 0),
  );

  final List<GpsSample> _buffer = [];
  StreamSubscription<Position>? _positionSubscription;
  Timer? _flushTimer;
  bool _flushing = false;
  bool _disposed = false;
  int _deviceSequence = 0;

  Future<void> start() async {
    _update(phase: GpsTrackerPhase.starting);
    final serviceEnabled = await Geolocator.isLocationServiceEnabled();
    if (_disposed) return;
    if (!serviceEnabled) {
      _update(
        phase: GpsTrackerPhase.serviceDisabled,
        message: 'Location services are off. Turn them on to share bus location.',
      );
      return;
    }
    var permission = await Geolocator.checkPermission();
    if (permission == LocationPermission.denied) {
      permission = await Geolocator.requestPermission();
    }
    if (_disposed) return;
    if (permission == LocationPermission.denied ||
        permission == LocationPermission.deniedForever) {
      _update(
        phase: GpsTrackerPhase.permissionDenied,
        message: 'Location permission denied. Bus location will not be shared.',
      );
      return;
    }
    _positionSubscription = Geolocator.getPositionStream(
      locationSettings: const LocationSettings(
        accuracy: LocationAccuracy.high,
        distanceFilter: 15,
      ),
    ).listen(_onPosition, onError: (_) {
      _update(phase: GpsTrackerPhase.error, message: 'Location stream failed.');
    });
    _flushTimer = Timer.periodic(flushInterval, (_) => _flush());
    _update(phase: GpsTrackerPhase.tracking);
  }

  void _onPosition(Position position) {
    if (_disposed) return;
    final sample = GpsSample(
      tripId: tripId,
      latitude: position.latitude,
      longitude: position.longitude,
      occurredAt: position.timestamp,
      deviceSequence: _deviceSequence++,
      accuracyMeters: position.accuracy,
      altitudeMeters: position.altitude,
      speedMps: position.speed >= 0 ? position.speed : null,
      headingDegrees:
          position.heading >= 0 && position.heading < 360 ? position.heading : null,
    );
    _buffer.add(sample);
    if (_buffer.length > maxBufferedSamples) {
      _buffer.removeRange(0, _buffer.length - maxBufferedSamples);
    }
    _update(lastFixAt: sample.occurredAt, pendingCount: _buffer.length);
    if (_buffer.length >= flushThreshold) {
      unawaited(_flush());
    }
  }

  Future<void> _flush() async {
    if (_disposed || _flushing || _buffer.isEmpty) return;
    _flushing = true;
    try {
      final batch = _buffer.take(HttpGpsSyncClient.maxBatchSize).toList();
      final acknowledged = await syncClient.syncSamples(
        samples: batch,
        clientDeviceId: clientDeviceId,
      );
      // Remove exactly the acknowledged batch; anything beyond it stays queued.
      final removeCount = acknowledged < 0
          ? 0
          : (acknowledged > _buffer.length ? _buffer.length : acknowledged);
      _buffer.removeRange(0, removeCount);
      _update(
        pendingCount: _buffer.length,
        syncedCount: snapshot.value.syncedCount + acknowledged,
      );
    } on GpsAuthFailure {
      onAuthFailure?.call();
    } on GpsPermanentFailure {
      // Bad payload would poison the queue; drop the offending batch.
      final drop = _buffer.length > HttpGpsSyncClient.maxBatchSize
          ? HttpGpsSyncClient.maxBatchSize
          : _buffer.length;
      _buffer.removeRange(0, drop);
      _update(pendingCount: _buffer.length);
    } on GpsTransientFailure {
      // Keep buffered; the next flush retries.
    } on AuthNetworkFailure {
      // Offline; keep buffered for the next flush.
    } on GpsSyncFailure catch (e) {
      _update(message: e.message);
    } finally {
      _flushing = false;
    }
  }

  /// Stops tracking and makes a best-effort final flush.
  Future<void> stop() async {
    _flushTimer?.cancel();
    _flushTimer = null;
    await _positionSubscription?.cancel();
    _positionSubscription = null;
    await _flush();
    if (!_disposed) {
      _update(phase: GpsTrackerPhase.stopped);
    }
  }

  void dispose() {
    _disposed = true;
    _flushTimer?.cancel();
    _positionSubscription?.cancel();
    snapshot.dispose();
  }

  void _update({
    GpsTrackerPhase? phase,
    int? pendingCount,
    int? syncedCount,
    DateTime? lastFixAt,
    String? message,
  }) {
    if (_disposed) return;
    final current = snapshot.value;
    snapshot.value = current.copyWith(
      phase: phase,
      pendingCount: pendingCount,
      syncedCount: syncedCount,
      lastFixAt: lastFixAt,
      message: message,
    );
  }
}
