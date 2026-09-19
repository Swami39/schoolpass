import 'dart:convert';

import '../http/authenticated_http_client.dart';
import 'academic_models.dart';

class AdminAcademicApiFailure implements Exception {
  AdminAcademicApiFailure(this.message);
  final String message;
}

class AdminAcademicUnauthorized implements Exception {}

class AdminAcademicApi {
  AdminAcademicApi(this._http);

  final AuthenticatedHttpClient _http;

  Future<List<AcademicYearItem>> fetchAcademicYears() => _list('api/v1/admin/academic-years', AcademicYearItem.fromJson);

  Future<List<SchoolClassItem>> fetchClasses() => _list('api/v1/admin/classes', SchoolClassItem.fromJson);

  Future<List<SectionItem>> fetchSections({String? classId}) {
    final path = classId == null ? 'api/v1/admin/sections' : 'api/v1/admin/sections?class_id=$classId';
    return _list(path, SectionItem.fromJson);
  }

  Future<List<SubjectItem>> fetchSubjects() => _list('api/v1/admin/subjects', SubjectItem.fromJson);

  Future<List<TeacherAssignmentItem>> fetchTeacherAssignments() =>
      _list('api/v1/admin/teacher-assignments', TeacherAssignmentItem.fromJson);

  Future<List<T>> _list<T>(String path, T Function(Map<String, dynamic>) map) async {
    final response = await _http.getJsonPath(path);
    if (response.statusCode == 401) throw AdminAcademicUnauthorized();
    if (response.statusCode != 200) {
      throw AdminAcademicApiFailure('Request failed (${response.statusCode})');
    }
    final decoded = jsonDecode(response.body);
    if (decoded is! Map<String, dynamic> || decoded['items'] is! List) {
      throw AdminAcademicApiFailure('Malformed list response');
    }
    return (decoded['items'] as List)
        .whereType<Map<String, dynamic>>()
        .map(map)
        .toList(growable: false);
  }
}
