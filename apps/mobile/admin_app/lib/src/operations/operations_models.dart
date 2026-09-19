class CardItem {
  const CardItem({required this.id, required this.status, this.hfUid});

  final String id;
  final String status;
  final String? hfUid;

  factory CardItem.fromJson(Map<String, dynamic> json) => CardItem(
        id: json['id'] as String,
        status: json['status'] as String,
        hfUid: json['hf_uid'] as String?,
      );
}

class CardAssignmentItem {
  const CardAssignmentItem({required this.id, required this.status, required this.physicalCardId});

  final String id;
  final String status;
  final String physicalCardId;

  factory CardAssignmentItem.fromJson(Map<String, dynamic> json) => CardAssignmentItem(
        id: json['id'] as String,
        status: json['status'] as String,
        physicalCardId: json['physical_card_id'] as String,
      );
}

class RfidReaderItem {
  const RfidReaderItem({required this.id, required this.name, required this.status});

  final String id;
  final String name;
  final String status;

  factory RfidReaderItem.fromJson(Map<String, dynamic> json) => RfidReaderItem(
        id: json['id'] as String,
        name: json['name'] as String,
        status: json['status'] as String,
      );
}

class RfidEventItem {
  const RfidEventItem({required this.id, required this.occurredAt, this.hfUid, this.processingStatus});

  final String id;
  final String occurredAt;
  final String? hfUid;
  final String? processingStatus;

  factory RfidEventItem.fromJson(Map<String, dynamic> json) => RfidEventItem(
        id: json['id'] as String,
        occurredAt: json['occurred_at'] as String,
        hfUid: json['hf_uid'] as String?,
        processingStatus: json['processing_status'] as String?,
      );
}

class BusItem {
  const BusItem({required this.id, required this.displayName, required this.status});

  final String id;
  final String displayName;
  final String status;

  factory BusItem.fromJson(Map<String, dynamic> json) => BusItem(
        id: json['id'] as String,
        displayName: (json['display_name'] ?? json['registration_number']) as String,
        status: json['status'] as String,
      );
}

class TripItem {
  const TripItem({required this.id, required this.status, required this.serviceDate});

  final String id;
  final String status;
  final String serviceDate;

  factory TripItem.fromJson(Map<String, dynamic> json) => TripItem(
        id: json['id'] as String,
        status: json['status'] as String,
        serviceDate: json['service_date'] as String,
      );
}

class OperationsOverview {
  const OperationsOverview({
    required this.activeBuses,
    required this.activeTrips,
    required this.activeTransportAssignments,
    required this.rfidEventsLast24h,
    required this.boardingEventsLast24h,
  });

  final int activeBuses;
  final int activeTrips;
  final int activeTransportAssignments;
  final int rfidEventsLast24h;
  final int boardingEventsLast24h;

  factory OperationsOverview.fromJson(Map<String, dynamic> json) => OperationsOverview(
        activeBuses: json['active_buses'] as int,
        activeTrips: json['active_trips'] as int,
        activeTransportAssignments: json['active_transport_assignments'] as int,
        rfidEventsLast24h: json['rfid_events_last_24h'] as int,
        boardingEventsLast24h: json['boarding_events_last_24h'] as int,
      );
}

class BoardingRecordItem {
  const BoardingRecordItem({
    required this.id,
    required this.eventType,
    required this.occurredAt,
    required this.studentId,
  });

  final String id;
  final String eventType;
  final String occurredAt;
  final String studentId;

  factory BoardingRecordItem.fromJson(Map<String, dynamic> json) => BoardingRecordItem(
        id: json['id'] as String,
        eventType: json['event_type'] as String,
        occurredAt: json['occurred_at'] as String,
        studentId: json['student_id'] as String,
      );
}

class LocationSampleItem {
  const LocationSampleItem({
    required this.id,
    required this.occurredAt,
    required this.latitude,
    required this.longitude,
  });

  final String id;
  final String occurredAt;
  final String latitude;
  final String longitude;

  factory LocationSampleItem.fromJson(Map<String, dynamic> json) => LocationSampleItem(
        id: json['id'] as String,
        occurredAt: json['occurred_at'] as String,
        latitude: json['latitude'].toString(),
        longitude: json['longitude'].toString(),
      );
}

class RouteItem {
  const RouteItem({required this.id, required this.name, required this.status});

  final String id;
  final String name;
  final String status;

  factory RouteItem.fromJson(Map<String, dynamic> json) => RouteItem(
        id: json['id'] as String,
        name: json['name'] as String,
        status: json['status'] as String,
      );
}

class TransportAttendantItem {
  const TransportAttendantItem({required this.id, required this.employeeCode, required this.status});

  final String id;
  final String employeeCode;
  final String status;

  factory TransportAttendantItem.fromJson(Map<String, dynamic> json) => TransportAttendantItem(
        id: json['id'] as String,
        employeeCode: json['employee_code'] as String,
        status: json['status'] as String,
      );
}

class TransportAssignmentItem {
  const TransportAssignmentItem({required this.id, required this.status, required this.studentId});

  final String id;
  final String status;
  final String studentId;

  factory TransportAssignmentItem.fromJson(Map<String, dynamic> json) => TransportAssignmentItem(
        id: json['id'] as String,
        status: json['status'] as String,
        studentId: json['student_id'] as String,
      );
}
