import 'dart:convert';

import '../api/teacher_errors.dart';
import '../http/authenticated_http_client.dart';
import 'teacher_notification_models.dart';

class TeacherNotificationsApi {
  TeacherNotificationsApi(this._http);

  final AuthenticatedHttpClient _http;

  Future<List<TeacherNotification>> fetchNotifications({int limit = 50}) async {
    final response = await _http.getJsonPath('/api/v1/teacher/notifications?limit=$limit');
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
        .map(TeacherNotification.fromJson)
        .toList();
  }

  Future<TeacherNotification> markRead(String notificationId) async {
    final response = await _http.postJsonPath('/api/v1/teacher/notifications/$notificationId/read');
    throwIfTeacherDenied(response.statusCode);
    if (response.statusCode != 200) {
      throw TeacherRequestFailure(response.statusCode);
    }
    final decoded = jsonDecode(response.body);
    if (decoded is! Map<String, dynamic>) {
      throw TeacherParseFailure();
    }
    return TeacherNotification.fromJson(decoded);
  }
}
