import 'package:uuid/uuid.dart';

/// A single GNSS fix scoped to a trip.
///
/// Serializes to the backend's `TransportGpsSampleRequest` shape for
/// `POST /api/v1/transport/gps/samples/sync`.
class GpsSample {
  GpsSample({
    required this.tripId,
    required this.latitude,
    required this.longitude,
    required this.occurredAt,
    required this.deviceSequence,
    this.busId,
    this.accuracyMeters,
    this.altitudeMeters,
    this.speedMps,
    this.headingDegrees,
    String? clientSampleId,
  }) : clientSampleId = clientSampleId ?? const Uuid().v4();

  final String clientSampleId;
  final String tripId;
  final double latitude;
  final double longitude;
  final DateTime occurredAt;
  final int deviceSequence;
  final String? busId;
  final double? accuracyMeters;
  final double? altitudeMeters;
  final double? speedMps;
  final double? headingDegrees;

  Map<String, dynamic> toJson() => {
        'client_sample_id': clientSampleId,
        'trip_id': tripId,
        'latitude': latitude,
        'longitude': longitude,
        'occurred_at': occurredAt.toUtc().toIso8601String(),
        'bus_id': busId,
        'accuracy_meters': accuracyMeters,
        'altitude_meters': altitudeMeters,
        'speed_mps': speedMps,
        'heading_degrees': headingDegrees,
        'device_sequence': deviceSequence,
        'source': 'phone_gnss',
      };
}
