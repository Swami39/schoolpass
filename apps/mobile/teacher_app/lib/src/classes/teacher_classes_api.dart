import 'dart:convert';

import '../http/authenticated_http_client.dart';
import 'teacher_class_models.dart';

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
      throw Exception('Failed to load classes (${response.statusCode})');
    }
    final body = jsonDecode(response.body) as Map<String, dynamic>;
    final items = body['items'] as List<dynamic>;
    return items.map((e) => TeacherClassAssignment.fromJson(e as Map<String, dynamic>)).toList();
  }
}
