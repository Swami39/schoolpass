import 'dart:convert';

import '../api/teacher_errors.dart';
import '../http/authenticated_http_client.dart';
import 'teacher_timetable_models.dart';

class TeacherTimetableApi {
  TeacherTimetableApi(this._http);

  final AuthenticatedHttpClient _http;

  Future<List<TeacherTimetablePeriod>> fetchTimetable() async {
    final response = await _http.getJsonPath('/api/v1/teacher/timetable');
    throwIfTeacherDenied(response.statusCode);
    if (response.statusCode != 200) {
      throw TeacherRequestFailure(response.statusCode);
    }
    final decoded = jsonDecode(response.body);
    if (decoded is! Map<String, dynamic> || decoded['items'] is! List) {
      throw TeacherParseFailure();
    }
    return (decoded['items'] as List)
        .whereType<Map<String, dynamic>>()
        .map(TeacherTimetablePeriod.fromJson)
        .toList();
  }

  Future<TeacherTimetablePeriod> updatePeriod({
    required String periodId,
    String? startsAt,
    String? endsAt,
  }) async {
    final response = await _http.patchJsonPath(
      '/api/v1/teacher/timetable/$periodId',
      body: jsonEncode({
        if (startsAt != null) 'starts_at': startsAt,
        if (endsAt != null) 'ends_at': endsAt,
      }),
    );
    throwIfTeacherDenied(response.statusCode);
    if (response.statusCode != 200) {
      throw TeacherRequestFailure(response.statusCode);
    }
    final decoded = jsonDecode(response.body);
    if (decoded is! Map<String, dynamic>) {
      throw TeacherParseFailure();
    }
    return TeacherTimetablePeriod.fromJson(decoded);
  }
}
