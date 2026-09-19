/// Teacher class NFC outbox and sync API contract.
library;

import 'models.dart' show OutboxSyncState;

class TeacherClassNfcOutboxEvent {
  TeacherClassNfcOutboxEvent({
    required this.localId,
    required this.clientEventId,
    required this.clientDeviceId,
    required this.sectionId,
    required this.cardUid,
    required this.occurredAt,
    required this.deviceSequence,
    required this.createdAt,
    required this.syncState,
    required this.attemptCount,
    this.lastAttemptedAt,
    this.lastError,
    this.rejectionCode,
    this.serverEventId,
    this.attendanceRecordId,
    this.acknowledgedAt,
  });

  final int localId;
  final String clientEventId;
  final String clientDeviceId;
  final String sectionId;
  final String cardUid;
  final DateTime occurredAt;
  final int deviceSequence;
  final DateTime createdAt;
  final OutboxSyncState syncState;
  final int attemptCount;
  final DateTime? lastAttemptedAt;
  final String? lastError;
  final String? rejectionCode;
  final String? serverEventId;
  final String? attendanceRecordId;
  final DateTime? acknowledgedAt;
}

class TeacherClassNfcSyncRequest {
  TeacherClassNfcSyncRequest({
    required this.clientEventId,
    required this.sectionId,
    required this.cardUid,
    required this.occurredAt,
    this.deviceSequence,
  });

  final String clientEventId;
  final String sectionId;
  final String cardUid;
  final DateTime occurredAt;
  final int? deviceSequence;

  Map<String, dynamic> toJson() => {
        'client_event_id': clientEventId,
        'section_id': sectionId,
        'card_uid': cardUid,
        'occurred_at': occurredAt.toUtc().toIso8601String(),
        if (deviceSequence != null) 'device_sequence': deviceSequence,
      };
}

class TeacherClassNfcSyncResponse {
  TeacherClassNfcSyncResponse({
    required this.result,
    required this.clientEventId,
    required this.serverEventId,
    this.attendanceRecordId,
    required this.occurredAt,
    required this.receivedAt,
    this.rejectionCode,
  });

  final String result;
  final String clientEventId;
  final String serverEventId;
  final String? attendanceRecordId;
  final DateTime occurredAt;
  final DateTime receivedAt;
  final String? rejectionCode;

  factory TeacherClassNfcSyncResponse.fromJson(Map<String, dynamic> json) {
    return TeacherClassNfcSyncResponse(
      result: json['result'] as String,
      clientEventId: json['client_event_id'] as String,
      serverEventId: json['server_event_id'] as String,
      attendanceRecordId: json['attendance_record_id'] as String?,
      occurredAt: DateTime.parse(json['occurred_at'] as String),
      receivedAt: DateTime.parse(json['received_at'] as String),
      rejectionCode: json['rejection_code'] as String?,
    );
  }
}

class NoActiveSectionError implements Exception {
  NoActiveSectionError([this.message = 'No class section selected for NFC scan']);

  final String message;

  @override
  String toString() => message;
}
