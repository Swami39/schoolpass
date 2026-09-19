import 'dart:math' as math;

/// Configurable GNSS sampling policy (pilot defaults).
class GpsSamplingPolicy {
  const GpsSamplingPolicy({
    this.minimumInterval = const Duration(seconds: 15),
    this.minimumDistanceMeters = 25,
    this.desiredAccuracyMeters = 50,
  });

  final Duration minimumInterval;
  final double minimumDistanceMeters;
  final double desiredAccuracyMeters;

  static const defaultPolicy = GpsSamplingPolicy();

  bool shouldCapture({
    required DateTime now,
    required DateTime? lastCapturedAt,
    required double? lastLatitude,
    required double? lastLongitude,
    required double latitude,
    required double longitude,
    required double? accuracyMeters,
  }) {
    if (lastCapturedAt == null) {
      return true;
    }
    if (now.difference(lastCapturedAt) < minimumInterval) {
      return false;
    }
    if (accuracyMeters != null && accuracyMeters > desiredAccuracyMeters * 3) {
      return false;
    }
    if (lastLatitude != null && lastLongitude != null) {
      final distance = _distanceMeters(
        lastLatitude,
        lastLongitude,
        latitude,
        longitude,
      );
      if (distance < minimumDistanceMeters) {
        return false;
      }
    }
    return true;
  }

  double _distanceMeters(
    double lat1,
    double lon1,
    double lat2,
    double lon2,
  ) {
    const earthRadius = 6371000.0;
    final dLat = _toRad(lat2 - lat1);
    final dLon = _toRad(lon2 - lon1);
    final a = math.sin(dLat / 2) * math.sin(dLat / 2) +
        math.cos(_toRad(lat1)) *
            math.cos(_toRad(lat2)) *
            math.sin(dLon / 2) *
            math.sin(dLon / 2);
    return earthRadius * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a));
  }

  double _toRad(double deg) => deg * math.pi / 180.0;
}
