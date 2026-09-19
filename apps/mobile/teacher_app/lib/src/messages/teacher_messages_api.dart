import 'dart:convert';

import '../api/teacher_errors.dart';
import '../http/authenticated_http_client.dart';

class TeacherMessageResult {
  const TeacherMessageResult({
    required this.messageId,
    required this.recipientCount,
    required this.created,
  });

  final String messageId;
  final int recipientCount;
  final bool created;
}

class TeacherMessagesApi {
  TeacherMessagesApi(this._http);

  final AuthenticatedHttpClient _http;

  Future<TeacherMessageResult> sendMessage({
    required String sectionId,
    required String title,
    required String body,
    required String idempotencyKey,
    String? studentId,
    bool urgent = false,
  }) async {
    final response = await _http.postJsonPath(
      '/api/v1/teacher/messages',
      body: jsonEncode({
        'section_id': sectionId,
        if (studentId != null) 'student_id': studentId,
        'title': title,
        'body': body,
        'urgent': urgent,
        'idempotency_key': idempotencyKey,
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
    return TeacherMessageResult(
      messageId: decoded['message_id'] as String,
      recipientCount: decoded['recipient_count'] as int,
      created: decoded['created'] as bool,
    );
  }
}
