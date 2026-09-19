import 'dart:convert';

import '../api/teacher_errors.dart';
import '../http/authenticated_http_client.dart';
import 'teacher_results_models.dart';

class TeacherResultsApi {
  TeacherResultsApi(this._http);

  final AuthenticatedHttpClient _http;

  Future<List<TeacherAssessment>> fetchAssessments(String sectionId) async {
    final response = await _http.getJsonPath('/api/v1/teacher/classes/$sectionId/assessments');
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
        .map(TeacherAssessment.fromJson)
        .toList();
  }

  Future<TeacherAssessmentMarks> fetchMarks(String assessmentId) async {
    final response = await _http.getJsonPath('/api/v1/teacher/assessments/$assessmentId/marks');
    throwIfTeacherDenied(response.statusCode);
    if (response.statusCode != 200) {
      throw TeacherRequestFailure(response.statusCode);
    }
    final decoded = jsonDecode(response.body);
    if (decoded is! Map<String, dynamic> || decoded['items'] is! List) {
      throw TeacherParseFailure();
    }
    return TeacherAssessmentMarks(
      assessmentId: decoded['assessment_id'] as String,
      maxMarks: decoded['max_marks'] as int,
      items: (decoded['items'] as List)
          .whereType<Map<String, dynamic>>()
          .map(TeacherStudentMark.fromJson)
          .toList(),
    );
  }

  Future<TeacherStudentMark> upsertMark({
    required String assessmentId,
    required String studentId,
    required int marks,
  }) async {
    final response = await _http.putJsonPath(
      '/api/v1/teacher/assessments/$assessmentId/students/$studentId/marks',
      body: jsonEncode({'marks': marks}),
    );
    throwIfTeacherDenied(response.statusCode);
    if (response.statusCode != 200) {
      throw TeacherRequestFailure(response.statusCode);
    }
    final decoded = jsonDecode(response.body);
    if (decoded is! Map<String, dynamic>) {
      throw TeacherParseFailure();
    }
    return TeacherStudentMark.fromJson(decoded);
  }
}
