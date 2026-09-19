import 'bus_location_errors.dart';

enum ParentBusLocationStatus {
  available('available'),
  noAssignment('no_assignment'),
  noActiveTrip('no_active_trip'),
  locationUnavailable('location_unavailable'),
  cacheUnavailable('cache_unavailable');

  const ParentBusLocationStatus(this.apiValue);

  final String apiValue;

  static ParentBusLocationStatus parse(String raw) {
    for (final value in ParentBusLocationStatus.values) {
      if (value.apiValue == raw) {
        return value;
      }
    }
    throw ParentBusLocationParseFailure('unknown status');
  }
}

/// Coordinates are only present when [ParentBusLocation.status] is [ParentBusLocationStatus.available].
class ParentBusLocationCoordinates {
  const ParentBusLocationCoordinates({
    required this.latitude,
    required this.longitude,
    required this.occurredAt,
    required this.receivedAt,
    this.accuracyMeters,
  });

  final double latitude;
  final double longitude;
  final DateTime occurredAt;
  final DateTime receivedAt;
  final double? accuracyMeters;
}

/// Typed current bus location for one child (server-authoritative fields only).
class ParentBusLocation {
  const ParentBusLocation({
    required this.studentId,
    required this.status,
    this.busId,
    this.tripId,
    this.coordinates,
  });

  final String studentId;
  final ParentBusLocationStatus status;
  final String? busId;
  final String? tripId;
  final ParentBusLocationCoordinates? coordinates;

  static ParentBusLocation parseJson(Map<String, dynamic> json) {
    final statusRaw = json['status'];
    if (statusRaw is! String) {
      throw ParentBusLocationParseFailure('missing status');
    }
    final status = ParentBusLocationStatus.parse(statusRaw);

    final studentRaw = json['student_id'];
    if (studentRaw is! String || studentRaw.isEmpty) {
      throw ParentBusLocationParseFailure('missing student_id');
    }

    final busId = _optionalString(json['bus_id']);
    final tripId = _optionalString(json['trip_id']);

    ParentBusLocationCoordinates? coordinates;
    if (status == ParentBusLocationStatus.available) {
      final latitude = _readRequiredDouble(json['latitude'], field: 'latitude');
      final longitude = _readRequiredDouble(json['longitude'], field: 'longitude');
      final occurredAt = _readRequiredDateTime(json['occurred_at'], field: 'occurred_at');
      final receivedAt = _readRequiredDateTime(json['received_at'], field: 'received_at');
      coordinates = ParentBusLocationCoordinates(
        latitude: latitude,
        longitude: longitude,
        occurredAt: occurredAt,
        receivedAt: receivedAt,
        accuracyMeters: _readOptionalDouble(json['accuracy_meters']),
      );
    }

    return ParentBusLocation(
      studentId: studentRaw,
      status: status,
      busId: busId,
      tripId: tripId,
      coordinates: coordinates,
    );
  }

  static String? _optionalString(Object? value) {
    if (value == null) {
      return null;
    }
    if (value is! String || value.isEmpty) {
      throw ParentBusLocationParseFailure('invalid id field');
    }
    return value;
  }

  static double? _readOptionalDouble(Object? value) {
    if (value == null) {
      return null;
    }
    return _readRequiredDouble(value, field: 'accuracy_meters');
  }

  static double _readRequiredDouble(Object? value, {required String field}) {
    if (value is num) {
      return value.toDouble();
    }
    if (value is String) {
      final parsed = double.tryParse(value);
      if (parsed != null) {
        return parsed;
      }
    }
    throw ParentBusLocationParseFailure('missing $field');
  }

  static DateTime _readRequiredDateTime(Object? value, {required String field}) {
    if (value is! String || value.isEmpty) {
      throw ParentBusLocationParseFailure('missing $field');
    }
    final parsed = DateTime.tryParse(value);
    if (parsed == null) {
      throw ParentBusLocationParseFailure('invalid $field');
    }
    return parsed.toUtc();
  }
}
