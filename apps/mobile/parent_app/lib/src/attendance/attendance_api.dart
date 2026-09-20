import 'dart:convert';

import '../http/authenticated_http_client.dart';
import 'attendance_models.dart';

class AttendanceApi {
  AttendanceApi(this._http);

  final AuthenticatedHttpClient _http;

  Future<List<AttendanceRecordItem>> fetchAttendance({
    required String studentId,
    String? onDate,
    String? fromDate,
    String? toDate,
    int limit = 30,
  }) async {
    final query = <String, String>{'limit': '$limit'};
    if (onDate != null) {
      query['date'] = onDate;
    }
    if (fromDate != null) {
      query['from_date'] = fromDate;
    }
    if (toDate != null) {
      query['to_date'] = toDate;
    }
    final queryString = query.entries.map((e) => '${e.key}=${Uri.encodeQueryComponent(e.value)}').join('&');
    final path = '/api/v1/parent/children/$studentId/attendance?$queryString';
    final response = await _http.getJsonPath(path);
    if (response.statusCode == 404) {
      throw AttendanceUnauthorized();
    }
    if (response.statusCode == 401 || response.statusCode == 403) {
      throw AttendanceUnauthorized();
    }
    if (response.statusCode != 200) {
      throw AttendanceRequestFailure(response.statusCode);
    }
    final decoded = jsonDecode(response.body);
    if (decoded is! Map<String, dynamic>) {
      throw AttendanceParseFailure();
    }
    final items = decoded['items'];
    if (items is! List) {
      throw AttendanceParseFailure();
    }
    return items
        .whereType<Map<String, dynamic>>()
        .map(AttendanceRecordItem.fromJson)
        .toList(growable: false);
  }
}

class AttendanceUnauthorized implements Exception {}

class AttendanceRequestFailure implements Exception {
  AttendanceRequestFailure(this.statusCode);
  final int statusCode;
}

class AttendanceParseFailure implements Exception {}
