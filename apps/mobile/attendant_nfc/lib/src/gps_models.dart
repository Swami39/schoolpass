import 'models.dart';

class GpsPosition {
  const GpsPosition({
    required this.latitude,
    required this.longitude,
    this.accuracyMeters,
    this.altitudeMeters,
    this.speedMps,
    this.headingDegrees,
    required this.occurredAt,
  });

  final double latitude;
  final double longitude;
  final double? accuracyMeters;
  final double? altitudeMeters;
  final double? speedMps;
  final double? headingDegrees;
  final DateTime occurredAt;
}

class GpsOutboxSample {
  GpsOutboxSample({
    required this.localId,
    required this.clientSampleId,
    required this.clientDeviceId,
    required this.tripId,
    required this.latitude,
    required this.longitude,
    this.accuracyMeters,
    this.altitudeMeters,
    this.speedMps,
    this.headingDegrees,
    required this.occurredAt,
    required this.localCreatedAt,
    required this.deviceSequence,
    required this.syncState,
    required this.attemptCount,
    this.lastAttemptedAt,
    this.lastError,
    this.rejectionCode,
    this.serverSampleId,
    this.acknowledgedAt,
  });

  final int localId;
  final String clientSampleId;
  final String clientDeviceId;
  final String tripId;
  final double latitude;
  final double longitude;
  final double? accuracyMeters;
  final double? altitudeMeters;
  final double? speedMps;
  final double? headingDegrees;
  final DateTime occurredAt;
  final DateTime localCreatedAt;
  final int deviceSequence;
  final OutboxSyncState syncState;
  final int attemptCount;
  final DateTime? lastAttemptedAt;
  final String? lastError;
  final String? rejectionCode;
  final String? serverSampleId;
  final DateTime? acknowledgedAt;
}

class TransportGpsSampleRequest {
  TransportGpsSampleRequest({
    required this.clientSampleId,
    required this.tripId,
    required this.latitude,
    required this.longitude,
    required this.occurredAt,
    required this.deviceSequence,
    this.accuracyMeters,
    this.altitudeMeters,
    this.speedMps,
    this.headingDegrees,
    this.source = 'phone_gnss',
  });

  final String clientSampleId;
  final String tripId;
  final double latitude;
  final double longitude;
  final DateTime occurredAt;
  final int deviceSequence;
  final double? accuracyMeters;
  final double? altitudeMeters;
  final double? speedMps;
  final double? headingDegrees;
  final String source;

  Map<String, dynamic> toJson() => {
        'client_sample_id': clientSampleId,
        'trip_id': tripId,
        'latitude': latitude.toString(),
        'longitude': longitude.toString(),
        'occurred_at': occurredAt.toUtc().toIso8601String(),
        'device_sequence': deviceSequence,
        'source': source,
        if (accuracyMeters != null) 'accuracy_meters': accuracyMeters.toString(),
        if (altitudeMeters != null) 'altitude_meters': altitudeMeters.toString(),
        if (speedMps != null) 'speed_mps': speedMps.toString(),
        if (headingDegrees != null) 'heading_degrees': headingDegrees.toString(),
      };
}

class TransportGpsSampleSyncResult {
  TransportGpsSampleSyncResult({
    required this.result,
    required this.clientSampleId,
    required this.serverSampleId,
    required this.occurredAt,
    required this.receivedAt,
    this.rejectionCode,
    this.deviceSequence,
  });

  final String result;
  final String clientSampleId;
  final String serverSampleId;
  final DateTime occurredAt;
  final DateTime receivedAt;
  final String? rejectionCode;
  final int? deviceSequence;

  factory TransportGpsSampleSyncResult.fromJson(Map<String, dynamic> json) {
    return TransportGpsSampleSyncResult(
      result: json['result'] as String,
      clientSampleId: json['client_sample_id'] as String,
      serverSampleId: json['server_sample_id'] as String,
      occurredAt: DateTime.parse(json['occurred_at'] as String),
      receivedAt: DateTime.parse(json['received_at'] as String),
      rejectionCode: json['rejection_code'] as String?,
      deviceSequence: json['device_sequence'] as int?,
    );
  }
}

class NoActiveTripForGpsError implements Exception {
  NoActiveTripForGpsError([this.message = 'No active trip for GPS capture']);

  final String message;

  @override
  String toString() => message;
}

const kGpsMaxBatchSize = 50;
