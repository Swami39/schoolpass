import 'package:sqlite3/sqlite3.dart';

import 'models.dart';
import 'teacher_models.dart';

const _metaDeviceSequenceKey = 'device_sequence';

class TeacherClassNfcOutboxStore {
  TeacherClassNfcOutboxStore._(this._db);

  final Database _db;

  static TeacherClassNfcOutboxStore open({required String path}) {
    final db = sqlite3.open(path);
    final store = TeacherClassNfcOutboxStore._(db);
    store._migrate();
    return store;
  }

  static TeacherClassNfcOutboxStore openInMemory() {
    final db = sqlite3.openInMemory();
    final store = TeacherClassNfcOutboxStore._(db);
    store._migrate();
    return store;
  }

  void close() => _db.dispose();

  void _migrate() {
    _db.execute('''
      CREATE TABLE IF NOT EXISTS device_meta (
        key TEXT PRIMARY KEY NOT NULL,
        value INTEGER NOT NULL
      );
    ''');
    _db.execute('''
      CREATE TABLE IF NOT EXISTS teacher_class_nfc_outbox (
        local_id INTEGER PRIMARY KEY AUTOINCREMENT,
        client_event_id TEXT NOT NULL UNIQUE,
        client_device_id TEXT NOT NULL,
        section_id TEXT NOT NULL,
        card_uid TEXT NOT NULL,
        occurred_at TEXT NOT NULL,
        device_sequence INTEGER NOT NULL,
        created_at TEXT NOT NULL,
        sync_state TEXT NOT NULL,
        attempt_count INTEGER NOT NULL DEFAULT 0,
        last_attempted_at TEXT,
        last_error TEXT,
        rejection_code TEXT,
        server_event_id TEXT,
        attendance_record_id TEXT,
        acknowledged_at TEXT
      );
    ''');
    _db.execute(
      'CREATE INDEX IF NOT EXISTS ix_teacher_nfc_outbox_pending '
      'ON teacher_class_nfc_outbox (sync_state, device_sequence ASC)',
    );
    _db.execute(
      "INSERT OR IGNORE INTO device_meta (key, value) VALUES ('$_metaDeviceSequenceKey', 0)",
    );
  }

  int recoverSyncingToPending() {
    _db.execute(
      'UPDATE teacher_class_nfc_outbox SET sync_state = ? WHERE sync_state = ?',
      [OutboxSyncState.pending.storageValue, OutboxSyncState.syncing.storageValue],
    );
    return _db.updatedRows;
  }

  int nextDeviceSequence() {
    _db.execute('BEGIN IMMEDIATE');
    try {
      final row = _db.select(
        'SELECT value FROM device_meta WHERE key = ?',
        [_metaDeviceSequenceKey],
      ).first;
      final next = (row['value'] as int) + 1;
      _db.execute(
        'UPDATE device_meta SET value = ? WHERE key = ?',
        [next, _metaDeviceSequenceKey],
      );
      _db.execute('COMMIT');
      return next;
    } catch (e) {
      _db.execute('ROLLBACK');
      rethrow;
    }
  }

  TeacherClassNfcOutboxEvent insertPendingEvent({
    required String clientEventId,
    required String clientDeviceId,
    required String sectionId,
    required String cardUid,
    required DateTime occurredAt,
    required int deviceSequence,
    required DateTime createdAt,
  }) {
    _db.execute('BEGIN IMMEDIATE');
    try {
      _db.execute(
        '''
        INSERT INTO teacher_class_nfc_outbox (
          client_event_id, client_device_id, section_id, card_uid,
          occurred_at, device_sequence, created_at, sync_state, attempt_count
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0)
        ''',
        [
          clientEventId,
          clientDeviceId,
          sectionId,
          cardUid,
          occurredAt.toUtc().toIso8601String(),
          deviceSequence,
          createdAt.toUtc().toIso8601String(),
          OutboxSyncState.pending.storageValue,
        ],
      );
      final localId = _db.lastInsertRowId;
      _db.execute('COMMIT');
      return getByLocalId(localId)!;
    } catch (e) {
      _db.execute('ROLLBACK');
      rethrow;
    }
  }

  TeacherClassNfcOutboxEvent? getByLocalId(int localId) {
    final rows = _db.select(
      'SELECT * FROM teacher_class_nfc_outbox WHERE local_id = ?',
      [localId],
    );
    if (rows.isEmpty) return null;
    return _rowToEvent(rows.first);
  }

  TeacherClassNfcOutboxEvent? claimNextPending() {
    _db.execute('BEGIN IMMEDIATE');
    try {
      final rows = _db.select(
        '''
        SELECT local_id FROM teacher_class_nfc_outbox
        WHERE sync_state = ?
        ORDER BY device_sequence ASC, local_id ASC
        LIMIT 1
        ''',
        [OutboxSyncState.pending.storageValue],
      );
      if (rows.isEmpty) {
        _db.execute('COMMIT');
        return null;
      }
      final localId = rows.first['local_id'] as int;
      _db.execute(
        '''
        UPDATE teacher_class_nfc_outbox SET sync_state = ?
        WHERE local_id = ? AND sync_state = ?
        ''',
        [OutboxSyncState.syncing.storageValue, localId, OutboxSyncState.pending.storageValue],
      );
      if (_db.updatedRows != 1) {
        _db.execute('COMMIT');
        return null;
      }
      _db.execute('COMMIT');
      return getByLocalId(localId);
    } catch (e) {
      _db.execute('ROLLBACK');
      rethrow;
    }
  }

  void markSyncAttemptStarted(int localId, DateTime attemptedAt) {
    _db.execute(
      '''
      UPDATE teacher_class_nfc_outbox
      SET attempt_count = attempt_count + 1, last_attempted_at = ?
      WHERE local_id = ? AND sync_state = ?
      ''',
      [
        attemptedAt.toUtc().toIso8601String(),
        localId,
        OutboxSyncState.syncing.storageValue,
      ],
    );
  }

  void returnToPending(int localId, {String? lastError}) {
    _db.execute(
      '''
      UPDATE teacher_class_nfc_outbox
      SET sync_state = ?, last_error = COALESCE(?, last_error)
      WHERE local_id = ?
      ''',
      [OutboxSyncState.pending.storageValue, lastError, localId],
    );
  }

  void applyServerAcknowledgement({
    required int localId,
    required OutboxSyncState terminalState,
    required TeacherClassNfcSyncResponse response,
    required DateTime acknowledgedAt,
  }) {
    _db.execute(
      '''
      UPDATE teacher_class_nfc_outbox SET
        sync_state = ?,
        server_event_id = ?,
        attendance_record_id = ?,
        rejection_code = ?,
        acknowledged_at = ?,
        last_error = NULL
      WHERE local_id = ? AND sync_state = ?
      ''',
      [
        terminalState.storageValue,
        response.serverEventId,
        response.attendanceRecordId,
        response.rejectionCode,
        acknowledgedAt.toUtc().toIso8601String(),
        localId,
        OutboxSyncState.syncing.storageValue,
      ],
    );
  }

  void markRejectedFromClientHttp({
    required int localId,
    required String lastError,
    required DateTime acknowledgedAt,
  }) {
    _db.execute(
      '''
      UPDATE teacher_class_nfc_outbox SET
        sync_state = ?,
        last_error = ?,
        acknowledged_at = ?
      WHERE local_id = ?
      ''',
      [
        OutboxSyncState.rejected.storageValue,
        lastError,
        acknowledgedAt.toUtc().toIso8601String(),
        localId,
      ],
    );
  }

  TeacherClassNfcOutboxEvent _rowToEvent(Row row) {
    return TeacherClassNfcOutboxEvent(
      localId: row['local_id'] as int,
      clientEventId: row['client_event_id'] as String,
      clientDeviceId: row['client_device_id'] as String,
      sectionId: row['section_id'] as String,
      cardUid: row['card_uid'] as String,
      occurredAt: DateTime.parse(row['occurred_at'] as String),
      deviceSequence: row['device_sequence'] as int,
      createdAt: DateTime.parse(row['created_at'] as String),
      syncState: OutboxSyncState.fromStorage(row['sync_state'] as String),
      attemptCount: row['attempt_count'] as int,
      lastAttemptedAt: row['last_attempted_at'] == null
          ? null
          : DateTime.parse(row['last_attempted_at'] as String),
      lastError: row['last_error'] as String?,
      rejectionCode: row['rejection_code'] as String?,
      serverEventId: row['server_event_id'] as String?,
      attendanceRecordId: row['attendance_record_id'] as String?,
      acknowledgedAt: row['acknowledged_at'] == null
          ? null
          : DateTime.parse(row['acknowledged_at'] as String),
    );
  }
}
