import 'dart:io';

import 'package:attendant_nfc/attendant_nfc.dart';
import 'package:test/test.dart';

void main() {
  group('GPS outbox batch sync', () {
    late Directory tempDir;
    late String dbPath;

    setUp(() {
      tempDir = Directory.systemTemp.createTempSync('attendant_gps_test_');
      dbPath = '${tempDir.path}/attendant.db';
    });

    tearDown(() {
      tempDir.deleteSync(recursive: true);
    });

    (GpsSampleService, FakeTransportGpsSyncClient, GpsSyncWorker, GpsOutboxStore) harness() {
      final store = GpsOutboxStore.open(path: dbPath);
      final trip = MutableTripContext()
        ..setTrip(const TripSelection(tripId: 'trip-1'));
      final client = FakeTransportGpsSyncClient();
      final worker = GpsSyncWorker(store: store, client: client, clientDeviceId: 'dev-1');
      final service = GpsSampleService(
        store: store,
        tripContext: trip,
        clientDeviceId: 'dev-1',
        syncWorker: worker,
        policy: const GpsSamplingPolicy(minimumInterval: Duration.zero),
      );
      return (service, client, worker, store);
    }

    GpsPosition point({DateTime? at, double lat = 12.97, double lon = 77.59}) => GpsPosition(
          latitude: lat,
          longitude: lon,
          accuracyMeters: 10,
          occurredAt: at ?? DateTime.now().toUtc(),
        );

    test('1 offline sample persisted', () {
      final (service, _, _, store) = harness();
      final row = service.capturePosition(point());
      expect(row.syncState, OutboxSyncState.pending);
      expect(store.countBySyncState(OutboxSyncState.pending), 1);
    });

    test('2 survives restart', () {
      final (service, _, _, _) = harness();
      final row = service.capturePosition(point());
      final store2 = GpsOutboxStore.open(path: dbPath);
      expect(store2.getByClientSampleId(row.clientSampleId)?.syncState, OutboxSyncState.pending);
      store2.close();
    });

    test('3 client_sample_id stable on retry', () async {
      final (service, client, worker, _) = harness();
      final row = service.capturePosition(point());
      client.nextError = SyncTransientFailure('net');
      await worker.drainPending();
      client.handler = ({required samples, required clientDeviceId}) async {
        expect(samples.single.clientSampleId, row.clientSampleId);
        return [
          TransportGpsSampleSyncResult(
            result: 'processed',
            clientSampleId: samples.single.clientSampleId,
            serverSampleId: 'srv-1',
            occurredAt: samples.single.occurredAt,
            receivedAt: DateTime.now().toUtc(),
          ),
        ];
      };
      await worker.drainPending();
    });

    test('4 occurred_at stable on retry', () async {
      final store = GpsOutboxStore.open(path: dbPath);
      final client = FakeTransportGpsSyncClient();
      final worker = GpsSyncWorker(store: store, client: client, clientDeviceId: 'd1');
      final occurred = DateTime.utc(2026, 4, 1, 9, 0);
      store.insertPending(
        clientSampleId: 's1',
        clientDeviceId: 'd1',
        tripId: 't1',
        latitude: 1,
        longitude: 2,
        occurredAt: occurred,
        localCreatedAt: occurred,
        deviceSequence: store.nextDeviceSequence(),
      );
      client.nextError = SyncTransientFailure('net');
      await worker.drainPending();
      client.handler = ({required samples, required clientDeviceId}) async {
        expect(samples.single.occurredAt.toUtc(), occurred);
        return [
          TransportGpsSampleSyncResult(
            result: 'processed',
            clientSampleId: 's1',
            serverSampleId: 'srv',
            occurredAt: samples.single.occurredAt,
            receivedAt: DateTime.now().toUtc(),
          ),
        ];
      };
      await worker.drainPending();
    });

    test('5 device sequence stable on retry', () async {
      final store = GpsOutboxStore.open(path: dbPath);
      final client = FakeTransportGpsSyncClient();
      final worker = GpsSyncWorker(store: store, client: client, clientDeviceId: 'd1');
      final seq = store.nextDeviceSequence();
      store.insertPending(
        clientSampleId: 's-seq',
        clientDeviceId: 'd1',
        tripId: 't1',
        latitude: 1,
        longitude: 2,
        occurredAt: DateTime.now().toUtc(),
        localCreatedAt: DateTime.now().toUtc(),
        deviceSequence: seq,
      );
      client.handler = ({required samples, required clientDeviceId}) async {
        expect(samples.single.deviceSequence, seq);
        return [
          TransportGpsSampleSyncResult(
            result: 'processed',
            clientSampleId: samples.single.clientSampleId,
            serverSampleId: 'srv',
            occurredAt: samples.single.occurredAt,
            receivedAt: DateTime.now().toUtc(),
          ),
        ];
      };
      await worker.drainPending();
    });

    test('6 network failure returns to pending', () async {
      final (service, client, worker, store) = harness();
      service.capturePosition(point());
      client.nextError = SyncTransientFailure('net');
      await worker.drainPending();
      expect(store.countBySyncState(OutboxSyncState.pending), 1);
    });

    test('7 duplicate outcome', () async {
      final (service, client, worker, store) = harness();
      service.capturePosition(point());
      client.handler = ({required samples, required clientDeviceId}) async {
        return [
          TransportGpsSampleSyncResult(
            result: 'duplicate',
            clientSampleId: samples.single.clientSampleId,
            serverSampleId: 'srv-d',
            occurredAt: samples.single.occurredAt,
            receivedAt: DateTime.now().toUtc(),
          ),
        ];
      };
      await worker.drainPending();
      expect(store.countBySyncState(OutboxSyncState.duplicate), 1);
    });

    test('8 rejection outcome', () async {
      final (service, client, worker, store) = harness();
      service.capturePosition(point());
      client.handler = ({required samples, required clientDeviceId}) async {
        return [
          TransportGpsSampleSyncResult(
            result: 'rejected',
            clientSampleId: samples.single.clientSampleId,
            serverSampleId: 'srv-r',
            occurredAt: samples.single.occurredAt,
            receivedAt: DateTime.now().toUtc(),
            rejectionCode: 'invalid_trip_phase',
          ),
        ];
      };
      await worker.drainPending();
      expect(store.countBySyncState(OutboxSyncState.rejected), 1);
    });

    test('9 restart recovers syncing', () {
      final store = GpsOutboxStore.open(path: dbPath);
      store.insertPending(
        clientSampleId: 'x',
        clientDeviceId: 'd1',
        tripId: 't1',
        latitude: 1,
        longitude: 2,
        occurredAt: DateTime.now().toUtc(),
        localCreatedAt: DateTime.now().toUtc(),
        deviceSequence: store.nextDeviceSequence(),
      );
      store.claimPendingBatch();
      store.close();
      final store2 = GpsOutboxStore.open(path: dbPath);
      store2.recoverSyncingToPending();
      expect(store2.countBySyncState(OutboxSyncState.pending), 1);
    });

    test('10 multiple samples batched', () async {
      final (service, client, worker, _) = harness();
      service.capturePosition(point());
      service.capturePosition(point(at: DateTime.now().toUtc().add(const Duration(seconds: 1)), lat: 13.1));
      client.handler = ({required samples, required clientDeviceId}) async {
        expect(samples.length, 2);
        return [
          for (final s in samples)
            TransportGpsSampleSyncResult(
              result: 'processed',
              clientSampleId: s.clientSampleId,
              serverSampleId: 'srv-${s.clientSampleId}',
              occurredAt: s.occurredAt,
              receivedAt: DateTime.now().toUtc(),
            ),
        ];
      };
      await worker.drainPending();
      expect(client.batches.single.length, 2);
    });

    test('11 batch size limit respected', () {
      final store = GpsOutboxStore.open(path: dbPath);
      for (var i = 0; i < 55; i++) {
        store.insertPending(
          clientSampleId: 's-$i',
          clientDeviceId: 'd1',
          tripId: 't1',
          latitude: 1,
          longitude: 2,
          occurredAt: DateTime.now().toUtc(),
          localCreatedAt: DateTime.now().toUtc(),
          deviceSequence: store.nextDeviceSequence(),
        );
      }
      expect(store.claimPendingBatch(limit: kGpsMaxBatchSize).length, kGpsMaxBatchSize);
    });

    test('12 acknowledged rows retained', () async {
      final (service, client, worker, store) = harness();
      final row = service.capturePosition(point());
      client.handler = ({required samples, required clientDeviceId}) async {
        return [
          TransportGpsSampleSyncResult(
            result: 'processed',
            clientSampleId: samples.single.clientSampleId,
            serverSampleId: 'srv',
            occurredAt: samples.single.occurredAt,
            receivedAt: DateTime.now().toUtc(),
          ),
        ];
      };
      await worker.drainPending();
      expect(store.getByClientSampleId(row.clientSampleId), isNotNull);
    });

    test('13 mixed batch outcomes', () async {
      final store = GpsOutboxStore.open(path: dbPath);
      final client = FakeTransportGpsSyncClient();
      final worker = GpsSyncWorker(store: store, client: client, clientDeviceId: 'd1');
      store.insertPending(
        clientSampleId: 'ok',
        clientDeviceId: 'd1',
        tripId: 't1',
        latitude: 1,
        longitude: 2,
        occurredAt: DateTime.now().toUtc(),
        localCreatedAt: DateTime.now().toUtc(),
        deviceSequence: store.nextDeviceSequence(),
      );
      store.insertPending(
        clientSampleId: 'bad',
        clientDeviceId: 'd1',
        tripId: 't1',
        latitude: 1,
        longitude: 2,
        occurredAt: DateTime.now().toUtc(),
        localCreatedAt: DateTime.now().toUtc(),
        deviceSequence: store.nextDeviceSequence(),
      );
      client.handler = ({required samples, required clientDeviceId}) async {
        return [
          TransportGpsSampleSyncResult(
            result: 'processed',
            clientSampleId: 'ok',
            serverSampleId: 'a',
            occurredAt: samples.first.occurredAt,
            receivedAt: DateTime.now().toUtc(),
          ),
          TransportGpsSampleSyncResult(
            result: 'rejected',
            clientSampleId: 'bad',
            serverSampleId: 'b',
            occurredAt: samples.last.occurredAt,
            receivedAt: DateTime.now().toUtc(),
            rejectionCode: 'invalid_trip',
          ),
        ];
      };
      await worker.drainPending();
      expect(store.countBySyncState(OutboxSyncState.processed), 1);
      expect(store.countBySyncState(OutboxSyncState.rejected), 1);
    });

    test('14 no active trip blocks capture', () {
      final store = GpsOutboxStore.open(path: dbPath);
      final service = GpsSampleService(
        store: store,
        tripContext: MutableTripContext(),
        clientDeviceId: 'd1',
        syncWorker: GpsSyncWorker(store: store, client: FakeTransportGpsSyncClient(), clientDeviceId: 'd1'),
        policy: const GpsSamplingPolicy(minimumInterval: Duration.zero),
      );
      expect(() => service.capturePosition(point()), throwsA(isA<NoActiveTripForGpsError>()));
    });

    test('15 fake adapter supplies deterministic points', () async {
      final adapter = FakeGpsAdapter();
      final pos = GpsPosition(
        latitude: 10.5,
        longitude: 20.5,
        occurredAt: DateTime.utc(2026, 1, 1),
      );
      final first = adapter.positions.first;
      adapter.emit(pos);
      expect(await first, pos);
    });
  });
}
