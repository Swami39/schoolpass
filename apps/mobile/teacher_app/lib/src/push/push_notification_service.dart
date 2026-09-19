import 'dart:convert';

import '../http/authenticated_http_client.dart';

/// Platform abstraction for FCM/APNs token acquisition.
abstract class PlatformPushProvider {
  Future<String?> obtainToken();
  Future<bool> requestPermission();
}

class PushNotificationService {
  PushNotificationService({
    required PlatformPushProvider provider,
    required AuthenticatedHttpClient http,
    this.platformName = 'android',
  })  : _provider = provider,
        _http = http;

  final PlatformPushProvider _provider;
  final AuthenticatedHttpClient _http;
  final String platformName;

  String? _lastRegisteredToken;

  Future<bool> ensurePermission() => _provider.requestPermission();

  Future<void> registerDeviceIfNeeded() async {
    final token = await _provider.obtainToken();
    if (token == null || token.isEmpty) {
      return;
    }
    if (token == _lastRegisteredToken) {
      return;
    }
    final body = jsonEncode({
      'platform': platformName,
      'fcm_token': token,
    });
    final response = await _http.postJsonPath('/api/v1/parent/push-devices', body: body);
    if (response.statusCode == 200 || response.statusCode == 201) {
      _lastRegisteredToken = token;
      return;
    }
    throw PushRegistrationFailure(response.statusCode);
  }

  void clearLocalRegistrationState() {
    _lastRegisteredToken = null;
  }
}

class PushRegistrationFailure implements Exception {
  PushRegistrationFailure(this.statusCode);
  final int statusCode;
}

class FakePlatformPushProvider implements PlatformPushProvider {
  FakePlatformPushProvider({this.token, this.permissionGranted = true});

  String? token;
  bool permissionGranted;
  int permissionCalls = 0;
  int tokenCalls = 0;

  @override
  Future<String?> obtainToken() async {
    tokenCalls += 1;
    return token;
  }

  @override
  Future<bool> requestPermission() async {
    permissionCalls += 1;
    return permissionGranted;
  }
}
