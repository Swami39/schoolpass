import 'dart:io';

import 'package:attendant_nfc/attendant_nfc.dart';
import 'package:test/test.dart';

void main() {
  group('NFC outbox and sync', () {
    late Directory tempDir;
    late String dbPath;

    setUp(() {
      tempDir = Directory.systemTemp.createTempSync('attendant_nfc_test_');
      dbPath = '${tempDir.path}/outbox.db';
    });

    tearDown(() {
      tempDir.deleteSync(recursive: true);
    });

    NfcOutboxStore reopenStore() => NfcOutboxStore.open(path: dbPath);

    (NfcEventService, FakeTransportNfcSyncClient, NfcSyncWorker) harness({
      TripContext? tripContext,
      String deviceId = 'device-1',
    }) {
      final store = reopenStore();
      final trip = tripContext ??
          (MutableTripContext()
            ..setTrip(const TripSelection(tripId: 'trip-a')));
      final client = FakeTransportNfcSyncClient();
      final worker = NfcSyncWorker(
        store: store,
        client: client,
        clientDeviceId: deviceId,
        config: const SyncWorkerConfig(maxTransientAttempts: 3),
      );
      final service = NfcEventService(
        store: store,
        tripContext: trip,
        clientDeviceId: deviceId,
        syncWorker: worker,
      );
      return (service, client, worker);
    }

    test('1 offline scan creates durable pending event', () {
      final (service, _, _) = harness();
      final event = service.recordScan(
        cardUid: '04a1b2',
        eventType: NfcEventType.boarding,
      );
      expect(event.syncState, OutboxSyncState.pending);
      expect(event.clientEventId, isNotEmpty);
    });

    test('2 event survives repository restart', () {
      final (service, _, _) = harness();
      final event = service.recordScan(
        cardUid: 'uid-1',
        eventType: NfcEventType.boarding,
      );
      final store2 = reopenStore();
      final loaded = store2.getByClientEventId(event.clientEventId);
      expect(loaded?.syncState, OutboxSyncState.pending);
      expect(loaded?.cardUid, 'uid-1');
      store2.close();
    });

    test('3 client event id unchanged across retries', () async {
      final (service, client, worker) = harness();
      service.recordScan(cardUid: 'u1', eventType: NfcEventType.boarding);
      client.nextError = SyncTransientFailure('offline');
      await worker.drainPending();
      client.nextError = SyncTransientFailure('offline');
      await worker.drainPending();
      expect(client.calls, hasLength(2));
      expect(client.calls[0].clientEventId, client.calls[1].clientEventId);
    });

    test('4 device sequence increments monotonically', () {
      final (service, _, _) = harness();
      final a = service.recordScan(
        cardUid: 'a',
        eventType: NfcEventType.boarding,
      );
      final b = service.recordScan(
        cardUid: 'b',
        eventType: NfcEventType.boarding,
      );
      expect(b.deviceSequence, greaterThan(a.deviceSequence));
    });

    test('5 device sequence survives restart', () {
      final (service, _, _) = harness();
      final last = service.recordScan(
        cardUid: 'x',
        eventType: NfcEventType.boarding,
      );
      final store2 = reopenStore();
      expect(store2.peekDeviceSequence(), last.deviceSequence);
      store2.close();
    });

    test('6 successful sync becomes processed', () async {
      final (service, client, worker) = harness();
      service.recordScan(cardUid: 'ok', eventType: NfcEventType.boarding);
      client.handler = ({required request, required clientDeviceId}) async {
        return TransportNfcSyncResponse(
          result: 'processed',
          clientEventId: request.clientEventId,
          serverEventId: 'srv-1',
          boardingRecordId: 'br-1',
          occurredAt: request.occurredAt,
          receivedAt: DateTime.now().toUtc(),
        );
      };
      await worker.drainPending();
      final pending = reopenStore().listBySyncState(OutboxSyncState.processed);
      expect(pending, hasLength(1));
      expect(pending.first.serverEventId, 'srv-1');
      expect(pending.first.boardingRecordId, 'br-1');
    });

    test('7 duplicate server response becomes duplicate', () async {
      final (service, client, worker) = harness();
      service.recordScan(cardUid: 'dup', eventType: NfcEventType.boarding);
      client.handler = ({required request, required clientDeviceId}) async {
        return TransportNfcSyncResponse(
          result: 'duplicate',
          clientEventId: request.clientEventId,
          serverEventId: 'srv-dup',
          boardingRecordId: 'br-dup',
          occurredAt: request.occurredAt,
          receivedAt: DateTime.now().toUtc(),
        );
      };
      await worker.drainPending();
      final rows = reopenStore().listBySyncState(OutboxSyncState.duplicate);
      expect(rows.single.serverEventId, 'srv-dup');
    });

    test('8 server rejection becomes rejected', () async {
      final (service, client, worker) = harness();
      service.recordScan(cardUid: 'bad', eventType: NfcEventType.dropoff);
      client.handler = ({required request, required clientDeviceId}) async {
        return TransportNfcSyncResponse(
          result: 'rejected',
          clientEventId: request.clientEventId,
          serverEventId: 'srv-rej',
          boardingRecordId: null,
          occurredAt: request.occurredAt,
          receivedAt: DateTime.now().toUtc(),
          rejectionCode: 'boarding_required',
        );
      };
      await worker.drainPending();
      final row = reopenStore().listBySyncState(OutboxSyncState.rejected).single;
      expect(row.rejectionCode, 'boarding_required');
    });

    test('9 network failure returns syncing event to pending', () async {
      final store = reopenStore();
      final client = FakeTransportNfcSyncClient();
      final worker = NfcSyncWorker(
        store: store,
        client: client,
        clientDeviceId: 'd1',
        config: const SyncWorkerConfig(maxTransientAttempts: 10),
      );
      store.insertPendingEvent(
        clientEventId: 'ev-1',
        clientDeviceId: 'd1',
        eventType: NfcEventType.boarding,
        cardUid: 'c',
        tripId: 't1',
        occurredAt: DateTime.now().toUtc(),
        deviceSequence: store.nextDeviceSequence(),
        createdAt: DateTime.now().toUtc(),
      );
      store.claimNextPending();
      worker.recoverOnStartup();
      client.nextError = SyncTransientFailure('network');
      await worker.drainPending();
      final row = store.getByClientEventId('ev-1')!;
      expect(row.syncState, OutboxSyncState.pending);
    });

    test('10 5xx returns event to pending', () async {
      final (service, client, worker) = harness();
      final created = service.recordScan(
        cardUid: 'c',
        eventType: NfcEventType.boarding,
      );
      client.nextError = SyncTransientFailure('server', statusCode: 503);
      await worker.drainPending();
      final row = reopenStore().getByClientEventId(created.clientEventId)!;
      expect(row.syncState, OutboxSyncState.pending);
    });

    test('11 permanent 4xx rejection does not retry forever', () async {
      final store = reopenStore();
      final client = FakeTransportNfcSyncClient();
      final worker = NfcSyncWorker(
        store: store,
        client: client,
        clientDeviceId: 'd1',
        config: const SyncWorkerConfig(maxTransientAttempts: 5),
      );
      store.insertPendingEvent(
        clientEventId: 'ev-http',
        clientDeviceId: 'd1',
        eventType: NfcEventType.boarding,
        cardUid: 'c',
        tripId: 't1',
        occurredAt: DateTime.now().toUtc(),
        deviceSequence: store.nextDeviceSequence(),
        createdAt: DateTime.now().toUtc(),
      );
      client.nextError = SyncPermanentHttpFailure('bad request', statusCode: 400);
      await worker.drainPending();
      final row = store.getByClientEventId('ev-http')!;
      expect(row.syncState, OutboxSyncState.rejected);
      client.nextError = SyncPermanentHttpFailure('bad request', statusCode: 400);
      await worker.drainPending();
      expect(client.calls, hasLength(1));
    });

    test('12 app restart recovers syncing events to pending', () {
      final store = reopenStore();
      store.insertPendingEvent(
        clientEventId: 'stuck',
        clientDeviceId: 'd1',
        eventType: NfcEventType.boarding,
        cardUid: 'c',
        tripId: 't1',
        occurredAt: DateTime.now().toUtc(),
        deviceSequence: store.nextDeviceSequence(),
        createdAt: DateTime.now().toUtc(),
      );
      final claimed = store.claimNextPending();
      expect(claimed!.syncState, OutboxSyncState.syncing);
      store.close();
      final store2 = reopenStore();
      store2.recoverSyncingToPending();
      expect(
        store2.getByClientEventId('stuck')!.syncState,
        OutboxSyncState.pending,
      );
      store2.close();
    });

    test('13 concurrent sync attempts do not process one event twice locally', () async {
      final store = reopenStore();
      final client = FakeTransportNfcSyncClient();
      var inFlight = 0;
      var maxInFlight = 0;
      client.handler = ({required request, required clientDeviceId}) async {
        inFlight++;
        maxInFlight = maxInFlight < inFlight ? inFlight : maxInFlight;
        await Future<void>.delayed(const Duration(milliseconds: 50));
        inFlight--;
        return TransportNfcSyncResponse(
          result: 'processed',
          clientEventId: request.clientEventId,
          serverEventId: 's1',
          boardingRecordId: 'b1',
          occurredAt: request.occurredAt,
          receivedAt: DateTime.now().toUtc(),
        );
      };
      store.insertPendingEvent(
        clientEventId: 'only-one',
        clientDeviceId: 'd1',
        eventType: NfcEventType.boarding,
        cardUid: 'c',
        tripId: 't1',
        occurredAt: DateTime.now().toUtc(),
        deviceSequence: store.nextDeviceSequence(),
        createdAt: DateTime.now().toUtc(),
      );
      final w1 = NfcSyncWorker(store: store, client: client, clientDeviceId: 'd1');
      final w2 = NfcSyncWorker(store: store, client: client, clientDeviceId: 'd1');
      await Future.wait([w1.drainPending(), w2.drainPending()]);
      expect(client.calls, hasLength(1));
      expect(maxInFlight, 1);
    });

    test('14 multiple queued events sync deterministically', () async {
      final (service, client, worker) = harness();
      service.recordScan(cardUid: 'first', eventType: NfcEventType.boarding);
      service.recordScan(cardUid: 'second', eventType: NfcEventType.boarding);
      final order = <String>[];
      client.handler = ({required request, required clientDeviceId}) async {
        order.add(request.cardUid);
        return TransportNfcSyncResponse(
          result: 'processed',
          clientEventId: request.clientEventId,
          serverEventId: 's-${order.length}',
          boardingRecordId: 'b-${order.length}',
          occurredAt: request.occurredAt,
          receivedAt: DateTime.now().toUtc(),
        );
      };
      await worker.drainPending();
      expect(order, ['first', 'second']);
    });

    test('15 no active trip prevents misleading event', () {
      final trip = MutableTripContext();
      final (service, _, _) = harness(tripContext: trip);
      expect(
        () => service.recordScan(
          cardUid: 'c',
          eventType: NfcEventType.boarding,
        ),
        throwsA(isA<NoActiveTripError>()),
      );
      final store = reopenStore();
      expect(store.listBySyncState(OutboxSyncState.pending), isEmpty);
      store.close();
    });

    test('16 optional trip_stop_id is preserved', () {
      final trip = MutableTripContext()
        ..setTrip(
          const TripSelection(tripId: 'trip-1', tripStopId: 'stop-9'),
        );
      final (service, _, _) = harness(tripContext: trip);
      final event = service.recordScan(
        cardUid: 'c',
        eventType: NfcEventType.boarding,
      );
      expect(event.tripStopId, 'stop-9');
    });

    test('17 server response ids are persisted', () async {
      final (service, client, worker) = harness();
      service.recordScan(cardUid: 'c', eventType: NfcEventType.boarding);
      client.handler = ({required request, required clientDeviceId}) async {
        return TransportNfcSyncResponse(
          result: 'processed',
          clientEventId: request.clientEventId,
          serverEventId: 'se-99',
          boardingRecordId: 'br-88',
          occurredAt: request.occurredAt,
          receivedAt: DateTime.now().toUtc(),
        );
      };
      await worker.drainPending();
      final row = reopenStore().listBySyncState(OutboxSyncState.processed).single;
      expect(row.serverEventId, 'se-99');
      expect(row.boardingRecordId, 'br-88');
      expect(row.acknowledgedAt, isNotNull);
    });

    test('18 outbox records not silently deleted after rejection', () async {
      final (service, client, worker) = harness();
      final created = service.recordScan(
        cardUid: 'c',
        eventType: NfcEventType.boarding,
      );
      client.handler = ({required request, required clientDeviceId}) async {
        return TransportNfcSyncResponse(
          result: 'rejected',
          clientEventId: request.clientEventId,
          serverEventId: 'srv',
          boardingRecordId: null,
          occurredAt: request.occurredAt,
          receivedAt: DateTime.now().toUtc(),
          rejectionCode: 'invalid_trip',
        );
      };
      await worker.drainPending();
      expect(reopenStore().getByClientEventId(created.clientEventId), isNotNull);
    });

    test('19 retry uses exact same client_event_id', () async {
      final (service, client, worker) = harness();
      service.recordScan(cardUid: 'c', eventType: NfcEventType.boarding);
      final id = client.calls.isEmpty
          ? reopenStore().listBySyncState(OutboxSyncState.pending).single.clientEventId
          : client.calls.first.clientEventId;
      client.nextError = SyncTransientFailure('timeout');
      await worker.drainPending();
      client.nextError = null;
      client.handler = ({required request, required clientDeviceId}) async {
        expect(request.clientEventId, id);
        return TransportNfcSyncResponse(
          result: 'processed',
          clientEventId: request.clientEventId,
          serverEventId: 's',
          boardingRecordId: 'b',
          occurredAt: request.occurredAt,
          receivedAt: DateTime.now().toUtc(),
        );
      };
      await worker.drainPending();
      expect(client.calls.last.clientEventId, id);
    });

    test('20 retry uses same occurred_at and device_sequence', () async {
      final store = reopenStore();
      final client = FakeTransportNfcSyncClient();
      final worker = NfcSyncWorker(
        store: store,
        client: client,
        clientDeviceId: 'd1',
      );
      final occurred = DateTime.utc(2026, 1, 2, 3, 4, 5);
      final seq = store.nextDeviceSequence();
      store.insertPendingEvent(
        clientEventId: 'fixed',
        clientDeviceId: 'd1',
        eventType: NfcEventType.boarding,
        cardUid: 'c',
        tripId: 't1',
        occurredAt: occurred,
        deviceSequence: seq,
        createdAt: occurred,
      );
      client.nextError = SyncTransientFailure('net');
      await worker.drainPending();
      client.handler = ({required request, required clientDeviceId}) async {
        expect(request.occurredAt.toUtc(), occurred);
        expect(request.deviceSequence, seq);
        return TransportNfcSyncResponse(
          result: 'processed',
          clientEventId: request.clientEventId,
          serverEventId: 's',
          boardingRecordId: 'b',
          occurredAt: request.occurredAt,
          receivedAt: DateTime.now().toUtc(),
        );
      };
      await worker.drainPending();
    });

    test('21 NFC adapter normalizes scanned UID', () async {
      final adapter = FakeNfcAdapter();
      final first = adapter.scans.first;
      adapter.emitRawUid('  04abc  ');
      expect((await first).cardUid, '04abc');
    });

    test('22 sync request json has no tenant_id', () async {
      final (service, client, worker) = harness();
      service.recordScan(cardUid: 'c', eventType: NfcEventType.boarding);
      client.handler = ({required request, required clientDeviceId}) async {
        final json = request.toJson();
        expect(json.containsKey('tenant_id'), isFalse);
        return TransportNfcSyncResponse(
          result: 'processed',
          clientEventId: request.clientEventId,
          serverEventId: 's',
          boardingRecordId: 'b',
          occurredAt: request.occurredAt,
          receivedAt: DateTime.now().toUtc(),
        );
      };
      await worker.drainPending();
    });
  });
}
