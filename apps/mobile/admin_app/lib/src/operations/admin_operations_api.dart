import 'dart:convert';

import '../http/authenticated_http_client.dart';
import 'operations_models.dart';

class AdminOperationsApiFailure implements Exception {
  AdminOperationsApiFailure(this.message);
  final String message;
}

class AdminOperationsUnauthorized implements Exception {}

class AdminOperationsApi {
  AdminOperationsApi(this._http);

  final AuthenticatedHttpClient _http;

  Future<List<CardItem>> fetchCards({String? search}) async {
    final path = search == null || search.isEmpty
        ? 'api/v1/admin/cards'
        : 'api/v1/admin/cards?hf_uid=${Uri.encodeQueryComponent(search)}';
    return _list(path, CardItem.fromJson);
  }

  Future<List<CardAssignmentItem>> fetchStudentCardAssignments(String studentId) =>
      _list('api/v1/admin/students/$studentId/card-assignments', CardAssignmentItem.fromJson);

  Future<CardAssignmentItem> assignCard({required String studentId, required String cardId}) async {
    return _mutate(
      'POST',
      'api/v1/admin/card-assignments',
      {'student_id': studentId, 'physical_card_id': cardId},
      CardAssignmentItem.fromJson,
    );
  }

  Future<List<RfidReaderItem>> fetchReaders() => _list('api/v1/admin/rfid-readers', RfidReaderItem.fromJson);

  Future<List<RfidEventItem>> fetchRfidEvents() => _list('api/v1/admin/rfid-events', RfidEventItem.fromJson);

  Future<List<BusItem>> fetchBuses() => _list('api/v1/admin/buses', BusItem.fromJson);

  Future<List<TripItem>> fetchTrips() => _list('api/v1/admin/trips', TripItem.fromJson);

  Future<OperationsOverview> fetchOperationsOverview() async {
    final response = await _http.getJsonPath('api/v1/admin/operations/overview');
    if (response.statusCode == 401) throw AdminOperationsUnauthorized();
    if (response.statusCode != 200) throw AdminOperationsApiFailure('Request failed (${response.statusCode})');
    final decoded = jsonDecode(response.body);
    if (decoded is! Map<String, dynamic>) throw AdminOperationsApiFailure('Malformed response');
    return OperationsOverview.fromJson(decoded);
  }

  Future<List<BoardingRecordItem>> fetchBoardingRecords() =>
      _list('api/v1/admin/boarding-records', BoardingRecordItem.fromJson);

  Future<List<LocationSampleItem>> fetchLocationSamples() =>
      _list('api/v1/admin/location-samples', LocationSampleItem.fromJson);

  Future<List<RouteItem>> fetchRoutes() => _list('api/v1/admin/routes', RouteItem.fromJson);

  Future<List<TransportAttendantItem>> fetchTransportAttendants() =>
      _list('api/v1/admin/transport-attendants', TransportAttendantItem.fromJson);

  Future<List<TransportAssignmentItem>> fetchTransportAssignments({String? studentId}) {
    final path = studentId == null
        ? 'api/v1/admin/transport-assignments'
        : 'api/v1/admin/transport-assignments?student_id=$studentId';
    return _list(path, TransportAssignmentItem.fromJson);
  }

  Future<T> _mutate<T>(
    String method,
    String path,
    Map<String, dynamic> body,
    T Function(Map<String, dynamic>) map,
  ) async {
    final encoded = jsonEncode(body);
    final response = method == 'POST'
        ? await _http.postJsonPath(path, body: encoded)
        : await _http.patchJsonPath(path, body: encoded);
    if (response.statusCode == 401) throw AdminOperationsUnauthorized();
    if (response.statusCode != 200) throw AdminOperationsApiFailure('Request failed (${response.statusCode})');
    final decoded = jsonDecode(response.body);
    if (decoded is! Map<String, dynamic>) throw AdminOperationsApiFailure('Malformed response');
    return map(decoded);
  }

  Future<List<T>> _list<T>(String path, T Function(Map<String, dynamic>) map) async {
    final response = await _http.getJsonPath(path);
    if (response.statusCode == 401) throw AdminOperationsUnauthorized();
    if (response.statusCode != 200) throw AdminOperationsApiFailure('Request failed (${response.statusCode})');
    final decoded = jsonDecode(response.body);
    if (decoded is! Map<String, dynamic> || decoded['items'] is! List) {
      throw AdminOperationsApiFailure('Malformed list response');
    }
    return (decoded['items'] as List).whereType<Map<String, dynamic>>().map(map).toList(growable: false);
  }
}
