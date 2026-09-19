import 'dart:convert';

import '../http/authenticated_http_client.dart';
import 'notification_models.dart';

class NotificationsApi {
  NotificationsApi(this._http);

  final AuthenticatedHttpClient _http;

  Future<List<ParentNotification>> fetchNotifications({int limit = 50}) async {
    final response = await _http.getJsonPath('/api/v1/parent/notifications?limit=$limit');
    if (response.statusCode == 401 || response.statusCode == 403) {
      throw NotificationsUnauthorized();
    }
    if (response.statusCode != 200) {
      throw NotificationsRequestFailure(response.statusCode);
    }
    return _parseList(response.body);
  }

  Future<ParentNotification> markRead(String notificationId) async {
    final response = await _http.postJsonPath('/api/v1/parent/notifications/$notificationId/read');
    if (response.statusCode == 404) {
      throw NotificationsNotFound();
    }
    if (response.statusCode == 401 || response.statusCode == 403) {
      throw NotificationsUnauthorized();
    }
    if (response.statusCode != 200) {
      throw NotificationsRequestFailure(response.statusCode);
    }
    final decoded = jsonDecode(response.body);
    if (decoded is! Map<String, dynamic>) {
      throw NotificationsParseFailure();
    }
    return ParentNotification.fromJson(decoded);
  }

  List<ParentNotification> _parseList(String body) {
    final decoded = jsonDecode(body);
    if (decoded is! Map<String, dynamic>) {
      throw NotificationsParseFailure();
    }
    final items = decoded['items'];
    if (items is! List) {
      throw NotificationsParseFailure();
    }
    return items
        .whereType<Map<String, dynamic>>()
        .map(ParentNotification.fromJson)
        .toList(growable: false);
  }
}

class NotificationsUnauthorized implements Exception {}

class NotificationsNotFound implements Exception {}

class NotificationsRequestFailure implements Exception {
  NotificationsRequestFailure(this.statusCode);
  final int statusCode;
}

class NotificationsParseFailure implements Exception {}
