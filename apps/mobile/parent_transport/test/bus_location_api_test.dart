import 'package:parent_transport/parent_transport.dart';
import 'package:test/test.dart';

void main() {
  const studentId = '550e8400-e29b-41d4-a716-446655440000';
  final apiOrigin = Uri(scheme: 'https', host: 'api.schoolpass.test');

  ParentBusLocationApi api(FakeParentBusLocationHttpTransport transport) =>
      ParentBusLocationApi(transport: transport, apiOrigin: apiOrigin);

  group('ParentBusLocationApi', () {
    late FakeParentBusLocationHttpTransport transport;
    late ParentBusLocationApi client;

    setUp(() {
      transport = FakeParentBusLocationHttpTransport();
      client = api(transport);
    });

    test('1 available response parses coordinates and metadata', () async {
      transport.handler = (_) async => ParentHttpResponse(
            statusCode: 200,
            body: '''
{
  "student_id": "$studentId",
  "status": "available",
  "bus_id": "11111111-1111-1111-1111-111111111111",
  "trip_id": "22222222-2222-2222-2222-222222222222",
  "latitude": "12.971600",
  "longitude": "77.594600",
  "occurred_at": "2026-09-19T08:00:00+00:00",
  "received_at": "2026-09-19T08:00:01+00:00",
  "accuracy_meters": "15.5"
}''',
          );

      final result = await client.fetchChildBusLocation(studentId: studentId);
      expect(result.status, ParentBusLocationStatus.available);
      expect(result.studentId, studentId);
      expect(result.busId, '11111111-1111-1111-1111-111111111111');
      expect(result.tripId, '22222222-2222-2222-2222-222222222222');
      final coords = result.coordinates!;
      expect(coords.latitude, closeTo(12.9716, 0.0001));
      expect(coords.longitude, closeTo(77.5946, 0.0001));
      expect(coords.accuracyMeters, closeTo(15.5, 0.01));
      expect(coords.occurredAt, DateTime.utc(2026, 9, 19, 8, 0));
      expect(coords.receivedAt, DateTime.utc(2026, 9, 19, 8, 0, 1));
    });

    test('2 no_assignment response', () async {
      transport.handler = (_) async => ParentHttpResponse(
            statusCode: 200,
            body: '{"student_id":"$studentId","status":"no_assignment"}',
          );
      final result = await client.fetchChildBusLocation(studentId: studentId);
      expect(result.status, ParentBusLocationStatus.noAssignment);
      expect(result.coordinates, isNull);
    });

    test('3 no_active_trip response', () async {
      transport.handler = (_) async => ParentHttpResponse(
            statusCode: 200,
            body:
                '{"student_id":"$studentId","status":"no_active_trip","bus_id":"11111111-1111-1111-1111-111111111111","trip_id":"22222222-2222-2222-2222-222222222222"}',
          );
      final result = await client.fetchChildBusLocation(studentId: studentId);
      expect(result.status, ParentBusLocationStatus.noActiveTrip);
      expect(result.coordinates, isNull);
    });

    test('4 location_unavailable response', () async {
      transport.handler = (_) async => ParentHttpResponse(
            statusCode: 200,
            body:
                '{"student_id":"$studentId","status":"location_unavailable","trip_id":"22222222-2222-2222-2222-222222222222"}',
          );
      final result = await client.fetchChildBusLocation(studentId: studentId);
      expect(result.status, ParentBusLocationStatus.locationUnavailable);
      expect(result.coordinates, isNull);
    });

    test('5 cache_unavailable response', () async {
      transport.handler = (_) async => ParentHttpResponse(
            statusCode: 200,
            body:
                '{"student_id":"$studentId","status":"cache_unavailable","trip_id":"22222222-2222-2222-2222-222222222222"}',
          );
      final result = await client.fetchChildBusLocation(studentId: studentId);
      expect(result.status, ParentBusLocationStatus.cacheUnavailable);
      expect(result.coordinates, isNull);
    });

    test('6 HTTP 404 maps to not found failure', () async {
      transport.handler = (_) async => ParentHttpResponse(statusCode: 404, body: '{}');
      expect(
        () => client.fetchChildBusLocation(studentId: studentId),
        throwsA(isA<ParentBusLocationNotFoundFailure>()),
      );
    });

    test('7 authentication failure maps to auth failure', () async {
      transport.handler = (_) async => ParentHttpResponse(statusCode: 401, body: '{}');
      expect(
        () => client.fetchChildBusLocation(studentId: studentId),
        throwsA(
          predicate((e) => e is ParentBusLocationAuthFailure && e.statusCode == 401),
        ),
      );
      transport.handler = (_) async => ParentHttpResponse(statusCode: 403, body: '{}');
      expect(
        () => client.fetchChildBusLocation(studentId: studentId),
        throwsA(
          predicate((e) => e is ParentBusLocationAuthFailure && e.statusCode == 403),
        ),
      );
    });

    test('8 network failure from transport', () async {
      transport.nextError = ParentBusLocationNetworkFailure();
      expect(
        () => client.fetchChildBusLocation(studentId: studentId),
        throwsA(isA<ParentBusLocationNetworkFailure>()),
      );
    });

    test('9 malformed JSON fails safely', () async {
      transport.handler = (_) async => ParentHttpResponse(statusCode: 200, body: '{');
      expect(
        () => client.fetchChildBusLocation(studentId: studentId),
        throwsA(isA<ParentBusLocationParseFailure>()),
      );
    });

    test('10 available without coordinates fails safely', () async {
      transport.handler = (_) async => ParentHttpResponse(
            statusCode: 200,
            body: '{"student_id":"$studentId","status":"available"}',
          );
      expect(
        () => client.fetchChildBusLocation(studentId: studentId),
        throwsA(isA<ParentBusLocationParseFailure>()),
      );
    });

    test('11 unexpected internal fields are ignored by typed model', () async {
      transport.handler = (_) async => ParentHttpResponse(
            statusCode: 200,
            body:
                '{"student_id":"$studentId","status":"no_assignment","tenant_id":"secret","guardian_id":"g1","attendant_id":"a1","client_device_id":"d1"}',
          );
      final result = await client.fetchChildBusLocation(studentId: studentId);
      expect(result.status, ParentBusLocationStatus.noAssignment);
      expect(result.studentId, studentId);
    });

    test('12 request uses GET path with student_id only', () async {
      transport.handler = (uri) async {
        expect(uri.scheme, 'https');
        expect(uri.host, 'api.schoolpass.test');
        expect(uri.path, '/api/v1/parent/children/$studentId/bus-location');
        expect(uri.query, isEmpty);
        expect(uri.queryParameters, isEmpty);
        return ParentHttpResponse(
          statusCode: 200,
          body: '{"student_id":"$studentId","status":"no_assignment"}',
        );
      };
      await client.fetchChildBusLocation(studentId: studentId);
      expect(transport.lastUri!.pathSegments.last, 'bus-location');
    });

    test('13 auth is delegated to transport layer', () async {
      var transportInvoked = false;
      transport.handler = (uri) async {
        transportInvoked = true;
        return ParentHttpResponse(
          statusCode: 200,
          body: '{"student_id":"$studentId","status":"no_assignment"}',
        );
      };
      await client.fetchChildBusLocation(studentId: studentId);
      expect(transportInvoked, isTrue);
      // ParentBusLocationApi has no headers/token API; app-owned transport owns auth.
      expect(client, isNot(isA<ParentBusLocationHttpTransport>()));
    });
  });
}
