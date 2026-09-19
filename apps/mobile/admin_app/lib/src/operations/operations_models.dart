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
