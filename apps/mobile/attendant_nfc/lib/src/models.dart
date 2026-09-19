/// Domain models for the NFC outbox and sync API contract.
library;

enum NfcEventType {
  boarding('boarding'),
  dropoff('dropoff');

  const NfcEventType(this.apiValue);
  final String apiValue;

  static NfcEventType fromApi(String value) {
    return NfcEventType.values.firstWhere(
      (e) => e.apiValue == value,
      orElse: () => throw ArgumentError('unknown event type: $value'),
    );
  }
}

enum OutboxSyncState {
  pending('pending'),
  syncing('syncing'),
  processed('processed'),
  duplicate('duplicate'),
  rejected('rejected');

  const OutboxSyncState(this.storageValue);
  final String storageValue;

  static OutboxSyncState fromStorage(String value) {
    return OutboxSyncState.values.firstWhere(
      (e) => e.storageValue == value,
      orElse: () => throw ArgumentError('unknown sync state: $value'),
    );
  }
}

class NfcOutboxEvent {
  NfcOutboxEvent({
    required this.localId,
    required this.clientEventId,
    required this.clientDeviceId,
    required this.eventType,
    required this.cardUid,
    required this.tripId,
    this.tripStopId,
    required this.occurredAt,
    required this.deviceSequence,
    required this.createdAt,
    required this.syncState,
    required this.attemptCount,
    this.lastAttemptedAt,
    this.lastError,
    this.rejectionCode,
    this.serverEventId,
    this.boardingRecordId,
    this.acknowledgedAt,
  });

  final int localId;
  final String clientEventId;
  final String clientDeviceId;
  final NfcEventType eventType;
  final String cardUid;
  final String tripId;
  final String? tripStopId;
  final DateTime occurredAt;
  final int deviceSequence;
  final DateTime createdAt;
  final OutboxSyncState syncState;
  final int attemptCount;
  final DateTime? lastAttemptedAt;
  final String? lastError;
  final String? rejectionCode;
  final String? serverEventId;
  final String? boardingRecordId;
  final DateTime? acknowledgedAt;

  NfcOutboxEvent copyWith({
    OutboxSyncState? syncState,
    int? attemptCount,
    DateTime? lastAttemptedAt,
    String? lastError,
    String? rejectionCode,
    String? serverEventId,
    String? boardingRecordId,
    DateTime? acknowledgedAt,
  }) {
    return NfcOutboxEvent(
      localId: localId,
      clientEventId: clientEventId,
      clientDeviceId: clientDeviceId,
      eventType: eventType,
      cardUid: cardUid,
      tripId: tripId,
      tripStopId: tripStopId,
      occurredAt: occurredAt,
      deviceSequence: deviceSequence,
      createdAt: createdAt,
      syncState: syncState ?? this.syncState,
      attemptCount: attemptCount ?? this.attemptCount,
      lastAttemptedAt: lastAttemptedAt ?? this.lastAttemptedAt,
      lastError: lastError ?? this.lastError,
      rejectionCode: rejectionCode ?? this.rejectionCode,
      serverEventId: serverEventId ?? this.serverEventId,
      boardingRecordId: boardingRecordId ?? this.boardingRecordId,
      acknowledgedAt: acknowledgedAt ?? this.acknowledgedAt,
    );
  }
}

/// Payload for POST /api/v1/transport/nfc/events/sync (no tenant_id).
class TransportNfcSyncRequest {
  TransportNfcSyncRequest({
    required this.clientEventId,
    required this.eventType,
    required this.cardUid,
    required this.occurredAt,
    required this.deviceSequence,
    required this.tripId,
    this.tripStopId,
  });

  final String clientEventId;
  final NfcEventType eventType;
  final String cardUid;
  final DateTime occurredAt;
  final int deviceSequence;
  final String tripId;
  final String? tripStopId;

  Map<String, dynamic> toJson() {
    return {
      'client_event_id': clientEventId,
      'event_type': eventType.apiValue,
      'card_uid': cardUid,
      'occurred_at': occurredAt.toUtc().toIso8601String(),
      'device_sequence': deviceSequence,
      'trip_id': tripId,
      if (tripStopId != null) 'trip_stop_id': tripStopId,
    };
  }
}

class TransportNfcSyncResponse {
  TransportNfcSyncResponse({
    required this.result,
    required this.clientEventId,
    required this.serverEventId,
    this.boardingRecordId,
    required this.occurredAt,
    required this.receivedAt,
    this.rejectionCode,
    this.deviceSequence,
  });

  final String result;
  final String clientEventId;
  final String serverEventId;
  final String? boardingRecordId;
  final DateTime occurredAt;
  final DateTime receivedAt;
  final String? rejectionCode;
  final int? deviceSequence;

  factory TransportNfcSyncResponse.fromJson(Map<String, dynamic> json) {
    return TransportNfcSyncResponse(
      result: json['result'] as String,
      clientEventId: json['client_event_id'] as String,
      serverEventId: json['server_event_id'] as String,
      boardingRecordId: json['boarding_record_id'] as String?,
      occurredAt: DateTime.parse(json['occurred_at'] as String),
      receivedAt: DateTime.parse(json['received_at'] as String),
      rejectionCode: json['rejection_code'] as String?,
      deviceSequence: json['device_sequence'] as int?,
    );
  }
}

class NoActiveTripError implements Exception {
  NoActiveTripError([this.message = 'No active trip selected for NFC scan']);

  final String message;

  @override
  String toString() => message;
}
