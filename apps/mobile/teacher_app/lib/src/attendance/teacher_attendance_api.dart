import 'dart:convert';

import '../api/teacher_errors.dart';
import '../http/authenticated_http_client.dart';
import 'teacher_attendance_models.dart';

class TeacherAttendanceApi {
  TeacherAttendanceApi(this._http);

  final AuthenticatedHttpClient _http;

  Future<List<TeacherAttendanceRecord>> fetchAttendance({
    required String sectionId,
    required String onDate,
  }) async {
    final response = await _http.getJsonPath(
      '/api/v1/teacher/classes/$sectionId/attendance?date=${Uri.encodeQueryComponent(onDate)}',
    );
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
        .map(TeacherAttendanceRecord.fromJson)
        .toList();
  }

  Future<TeacherAttendanceRecord> markAttendance({
    required String sectionId,
    required String onDate,
    required String studentId,
    required String status,
    String? reason,
  }) async {
    final response = await _http.postJsonPath(
      '/api/v1/teacher/classes/$sectionId/attendance?date=${Uri.encodeQueryComponent(onDate)}',
      body: jsonEncode({
        'student_id': studentId,
        'status': status,
        if (reason != null) 'reason': reason,
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
    return TeacherAttendanceRecord.fromJson(decoded);
  }
}
