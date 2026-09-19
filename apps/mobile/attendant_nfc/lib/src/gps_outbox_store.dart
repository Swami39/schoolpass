import 'package:sqlite3/sqlite3.dart';

import 'gps_models.dart';
import 'models.dart';

const _metaDeviceSequenceKey = 'device_sequence';

class GpsOutboxStore {
  GpsOutboxStore._(this._db);

  final Database _db;

  static GpsOutboxStore open({required String path}) {
    final db = sqlite3.open(path);
    final store = GpsOutboxStore._(db);
    store._migrate();
    return store;
  }

  static GpsOutboxStore openInMemory() {
    final db = sqlite3.openInMemory();
    final store = GpsOutboxStore._(db);
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
      CREATE TABLE IF NOT EXISTS gps_outbox (
        local_id INTEGER PRIMARY KEY AUTOINCREMENT,
        client_sample_id TEXT NOT NULL UNIQUE,
        client_device_id TEXT NOT NULL,
        trip_id TEXT NOT NULL,
        latitude REAL NOT NULL,
        longitude REAL NOT NULL,
        accuracy_meters REAL,
        altitude_meters REAL,
        speed_mps REAL,
        heading_degrees REAL,
        occurred_at TEXT NOT NULL,
        local_created_at TEXT NOT NULL,
        device_sequence INTEGER NOT NULL,
        sync_state TEXT NOT NULL,
        attempt_count INTEGER NOT NULL DEFAULT 0,
        last_attempted_at TEXT,
        last_error TEXT,
        rejection_code TEXT,
        server_sample_id TEXT,
        acknowledged_at TEXT
      );
    ''');
    _db.execute(
      'CREATE INDEX IF NOT EXISTS ix_gps_outbox_pending '
      'ON gps_outbox (sync_state, device_sequence ASC)',
    );
    _db.execute(
      "INSERT OR IGNORE INTO device_meta (key, value) VALUES ('$_metaDeviceSequenceKey', 0)",
    );
  }

  int recoverSyncingToPending() {
    _db.execute(
      "UPDATE gps_outbox SET sync_state = ? WHERE sync_state = ?",
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

  GpsOutboxSample insertPending({
    required String clientSampleId,
    required String clientDeviceId,
    required String tripId,
    required double latitude,
    required double longitude,
    required DateTime occurredAt,
    required DateTime localCreatedAt,
    required int deviceSequence,
    double? accuracyMeters,
    double? altitudeMeters,
    double? speedMps,
    double? headingDegrees,
  }) {
    _db.execute(
      '''
      INSERT INTO gps_outbox (
        client_sample_id, client_device_id, trip_id, latitude, longitude,
        accuracy_meters, altitude_meters, speed_mps, heading_degrees,
        occurred_at, local_created_at, device_sequence, sync_state, attempt_count
      ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0)
      ''',
      [
        clientSampleId,
        clientDeviceId,
        tripId,
        latitude,
        longitude,
        accuracyMeters,
        altitudeMeters,
        speedMps,
        headingDegrees,
        occurredAt.toUtc().toIso8601String(),
        localCreatedAt.toUtc().toIso8601String(),
        deviceSequence,
        OutboxSyncState.pending.storageValue,
      ],
    );
    return getByClientSampleId(clientSampleId)!;
  }

  GpsOutboxSample? getByClientSampleId(String clientSampleId) {
    final rows = _db.select(
      'SELECT * FROM gps_outbox WHERE client_sample_id = ?',
      [clientSampleId],
    );
    if (rows.isEmpty) {
      return null;
    }
    return _row(rows.first);
  }

  List<GpsOutboxSample> claimPendingBatch({int limit = kGpsMaxBatchSize}) {
    _db.execute('BEGIN IMMEDIATE');
    try {
      final rows = _db.select(
        '''
        SELECT local_id FROM gps_outbox
        WHERE sync_state = ?
        ORDER BY device_sequence ASC, local_id ASC
        LIMIT ?
        ''',
        [OutboxSyncState.pending.storageValue, limit],
      );
      if (rows.isEmpty) {
        _db.execute('COMMIT');
        return [];
      }
      final ids = [for (final r in rows) r['local_id'] as int];
      for (final id in ids) {
        _db.execute(
          '''
          UPDATE gps_outbox SET sync_state = ?
          WHERE local_id = ? AND sync_state = ?
          ''',
          [OutboxSyncState.syncing.storageValue, id, OutboxSyncState.pending.storageValue],
        );
      }
      _db.execute('COMMIT');
      return [
        for (final id in ids) getByLocalId(id)!,
      ];
    } catch (e) {
      _db.execute('ROLLBACK');
      rethrow;
    }
  }

  GpsOutboxSample? getByLocalId(int localId) {
    final rows = _db.select('SELECT * FROM gps_outbox WHERE local_id = ?', [localId]);
    if (rows.isEmpty) {
      return null;
    }
    return _row(rows.first);
  }

  void markBatchAttemptStarted(List<int> localIds, DateTime attemptedAt) {
    for (final id in localIds) {
      _db.execute(
        '''
        UPDATE gps_outbox
        SET attempt_count = attempt_count + 1, last_attempted_at = ?
        WHERE local_id = ? AND sync_state = ?
        ''',
        [
          attemptedAt.toUtc().toIso8601String(),
          id,
          OutboxSyncState.syncing.storageValue,
        ],
      );
    }
  }

  void returnBatchToPending(List<int> localIds, {String? lastError}) {
    for (final id in localIds) {
      _db.execute(
        '''
        UPDATE gps_outbox SET sync_state = ?, last_error = COALESCE(?, last_error)
        WHERE local_id = ?
        ''',
        [OutboxSyncState.pending.storageValue, lastError, id],
      );
    }
  }

  void applyResult({
    required int localId,
    required OutboxSyncState terminalState,
    required TransportGpsSampleSyncResult response,
    required DateTime acknowledgedAt,
  }) {
    _db.execute(
      '''
      UPDATE gps_outbox SET
        sync_state = ?,
        server_sample_id = ?,
        rejection_code = ?,
        acknowledged_at = ?,
        last_error = NULL
      WHERE local_id = ? AND sync_state = ?
      ''',
      [
        terminalState.storageValue,
        response.serverSampleId,
        response.rejectionCode,
        acknowledgedAt.toUtc().toIso8601String(),
        localId,
        OutboxSyncState.syncing.storageValue,
      ],
    );
  }

  void markBatchRejectedFromHttp(List<int> localIds, String lastError, DateTime at) {
    for (final id in localIds) {
      _db.execute(
        '''
        UPDATE gps_outbox SET sync_state = ?, last_error = ?, acknowledged_at = ?
        WHERE local_id = ?
        ''',
        [OutboxSyncState.rejected.storageValue, lastError, at.toUtc().toIso8601String(), id],
      );
    }
  }

  int countBySyncState(OutboxSyncState state) {
    final row = _db.select(
      'SELECT COUNT(*) AS c FROM gps_outbox WHERE sync_state = ?',
      [state.storageValue],
    ).first;
    return row['c'] as int;
  }

  GpsOutboxSample _row(Row row) {
    return GpsOutboxSample(
      localId: row['local_id'] as int,
      clientSampleId: row['client_sample_id'] as String,
      clientDeviceId: row['client_device_id'] as String,
      tripId: row['trip_id'] as String,
      latitude: (row['latitude'] as num).toDouble(),
      longitude: (row['longitude'] as num).toDouble(),
      accuracyMeters: row['accuracy_meters'] as double?,
      altitudeMeters: row['altitude_meters'] as double?,
      speedMps: row['speed_mps'] as double?,
      headingDegrees: row['heading_degrees'] as double?,
      occurredAt: DateTime.parse(row['occurred_at'] as String),
      localCreatedAt: DateTime.parse(row['local_created_at'] as String),
      deviceSequence: row['device_sequence'] as int,
      syncState: OutboxSyncState.fromStorage(row['sync_state'] as String),
      attemptCount: row['attempt_count'] as int,
      lastAttemptedAt: row['last_attempted_at'] == null
          ? null
          : DateTime.parse(row['last_attempted_at'] as String),
      lastError: row['last_error'] as String?,
      rejectionCode: row['rejection_code'] as String?,
      serverSampleId: row['server_sample_id'] as String?,
      acknowledgedAt: row['acknowledged_at'] == null
          ? null
          : DateTime.parse(row['acknowledged_at'] as String),
    );
  }
}
