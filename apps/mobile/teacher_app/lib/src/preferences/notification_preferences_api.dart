import 'dart:convert';

import '../http/authenticated_http_client.dart';

class NotificationPreferenceItem {
  const NotificationPreferenceItem({
    required this.notificationType,
    required this.pushEnabled,
  });

  final String notificationType;
  final bool pushEnabled;

  factory NotificationPreferenceItem.fromJson(Map<String, dynamic> json) {
    return NotificationPreferenceItem(
      notificationType: json['notification_type'] as String,
      pushEnabled: json['push_enabled'] as bool,
    );
  }

  Map<String, dynamic> toJson() => {
        'notification_type': notificationType,
        'push_enabled': pushEnabled,
      };
}

class NotificationPreferencesApi {
  NotificationPreferencesApi(this._http);

  final AuthenticatedHttpClient _http;

  Future<List<NotificationPreferenceItem>> fetchPreferences() async {
    final response = await _http.getJsonPath('/api/v1/parent/notification-preferences');
    if (response.statusCode != 200) {
      throw PreferencesRequestFailure(response.statusCode);
    }
    return _parseItems(response.body);
  }

  Future<List<NotificationPreferenceItem>> savePreferences(
    List<NotificationPreferenceItem> items,
  ) async {
    final body = jsonEncode({
      'items': items.map((e) => e.toJson()).toList(),
    });
    final response = await _http.putJsonPath('/api/v1/parent/notification-preferences', body: body);
    if (response.statusCode != 200) {
      throw PreferencesRequestFailure(response.statusCode);
    }
    return _parseItems(response.body);
  }

  List<NotificationPreferenceItem> _parseItems(String body) {
    final decoded = jsonDecode(body);
    if (decoded is! Map<String, dynamic>) {
      throw PreferencesParseFailure();
    }
    final items = decoded['items'];
    if (items is! List) {
      throw PreferencesParseFailure();
    }
    return items
        .whereType<Map<String, dynamic>>()
        .map(NotificationPreferenceItem.fromJson)
        .toList(growable: false);
  }
}

class PreferencesRequestFailure implements Exception {
  PreferencesRequestFailure(this.statusCode);
  final int statusCode;
}

class PreferencesParseFailure implements Exception {}
