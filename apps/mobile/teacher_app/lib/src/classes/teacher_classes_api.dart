import 'dart:convert';

import '../api/teacher_errors.dart';
import '../http/authenticated_http_client.dart';
import 'teacher_class_models.dart';
import 'teacher_student_models.dart';

class TeacherClassesUnauthorized implements Exception {}

class TeacherClassesApi {
  TeacherClassesApi(this._client);

  final AuthenticatedHttpClient _client;

  Future<List<TeacherClassAssignment>> fetchClasses() async {
    final response = await _client.getJsonPath('/api/v1/teacher/classes');
    if (response.statusCode == 401 || response.statusCode == 403) {
      throw TeacherClassesUnauthorized();
    }
    if (response.statusCode != 200) {
      throw TeacherRequestFailure(response.statusCode);
    }
    return _items(response.body, TeacherClassAssignment.fromJson);
  }

  Future<List<TeacherStudent>> fetchStudents(String sectionId) async {
    final response = await _client.getJsonPath('/api/v1/teacher/classes/$sectionId/students');
    throwIfTeacherDenied(response.statusCode);
    if (response.statusCode != 200) {
      throw TeacherRequestFailure(response.statusCode);
    }
    return _items(response.body, TeacherStudent.fromJson);
  }

  List<T> _items<T>(String body, T Function(Map<String, dynamic>) parse) {
    final decoded = jsonDecode(body);
    if (decoded is! Map<String, dynamic>) {
      throw TeacherParseFailure();
    }
    final items = decoded['items'];
    if (items is! List) {
      throw TeacherParseFailure();
    }
    return items.whereType<Map<String, dynamic>>().map(parse).toList();
  }
}
