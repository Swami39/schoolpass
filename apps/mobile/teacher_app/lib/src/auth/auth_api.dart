import 'dart:convert';

import 'package:http/http.dart' as http;

import 'auth_models.dart';

class AuthApi {
  AuthApi({required this.apiOrigin, http.Client? client}) : _client = client ?? http.Client();

  final Uri apiOrigin;
  final http.Client _client;

  Uri _uri(String path) => apiOrigin.resolve(path);

  Future<AuthTokens> passwordLogin({
    required String identifier,
    required String password,
  }) async {
    final response = await _client.post(
      _uri('api/v1/auth/password/login'),
      headers: {'content-type': 'application/json'},
      body: jsonEncode({'identifier': identifier, 'password': password}),
    );
    if (response.statusCode >= 500) {
      throw AuthNetworkFailure();
    }
    if (response.statusCode == 401) {
      throw AuthFailure('invalid credentials');
    }
    if (response.statusCode != 200) {
      throw AuthFailure('login failed');
    }
    return _parseTokenBody(response.body);
  }

  Future<AuthTokens> refresh({required String refreshToken}) async {
    final response = await _client.post(
      _uri('api/v1/auth/refresh'),
      headers: {'content-type': 'application/json'},
      body: jsonEncode({'refresh_token': refreshToken}),
    );
    if (response.statusCode >= 500 || response.statusCode == 0) {
      throw AuthNetworkFailure();
    }
    if (response.statusCode == 401) {
      throw AuthFailure('refresh expired');
    }
    if (response.statusCode != 200) {
      throw AuthFailure('refresh failed');
    }
    return _parseTokenBody(response.body);
  }

  Future<void> logout({required String accessToken}) async {
    await _client.post(
      _uri('api/v1/auth/logout'),
      headers: {'authorization': 'Bearer $accessToken'},
    );
  }

  AuthTokens _parseTokenBody(String body) {
    final Object? decoded;
    try {
      decoded = jsonDecode(body);
    } catch (_) {
      throw AuthFailure('malformed auth response');
    }
    if (decoded is! Map<String, dynamic>) {
      throw AuthFailure('malformed auth response');
    }
    if (decoded['mfa_required'] == true || decoded['enrollment_required'] == true) {
      throw AuthMfaRequired(decoded['mfa_token'] as String? ?? '');
    }
    final access = decoded['access_token'];
    final refresh = decoded['refresh_token'];
    if (access is! String || refresh is! String || access.isEmpty || refresh.isEmpty) {
      throw AuthFailure('malformed auth response');
    }
    return AuthTokens(accessToken: access, refreshToken: refresh);
  }
}
