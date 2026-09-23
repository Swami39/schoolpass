import 'dart:convert';

import '../api/attendant_errors.dart';
import '../http/authenticated_http_client.dart';
import 'trip_models.dart';

class AttendantTripsApi {
  AttendantTripsApi(this._http);

  final AuthenticatedHttpClient _http;

  Future<List<AttendantTrip>> fetchMyTripsToday() async {
    final response = await _http.getJsonPath('api/v1/transport-attendant/trips');
    throwIfAttendantDenied(response.statusCode);
    if (response.statusCode != 200) {
      throw AttendantRequestFailure(response.statusCode);
    }
    final decoded = jsonDecode(response.body);
    if (decoded is! Map<String, dynamic>) {
      throw AttendantParseFailure();
    }
    final items = decoded['items'];
    if (items is! List) {
      throw AttendantParseFailure();
    }
    return items
        .whereType<Map<String, dynamic>>()
        .map(AttendantTrip.fromJson)
        .toList();
  }

  Future<AttendantTrip> startTripBoarding(String tripId) async {
    final response = await _http.postJsonPath('api/v1/trips/$tripId/start');
    throwIfAttendantDenied(response.statusCode);
    if (response.statusCode != 200) {
      throw AttendantRequestFailure(response.statusCode);
    }
    final decoded = jsonDecode(response.body);
    if (decoded is! Map<String, dynamic>) {
      throw AttendantParseFailure();
    }
    return AttendantTrip.fromJson(decoded);
  }
}
