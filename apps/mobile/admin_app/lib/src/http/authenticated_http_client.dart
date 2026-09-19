import 'package:http/http.dart' as http;

import '../auth/auth_models.dart';
import '../auth/auth_repository.dart';

class MultipartFilePayload {
  const MultipartFilePayload({
    required this.filename,
    required this.bytes,
  });

  final String filename;
  final List<int> bytes;
}

class AuthenticatedHttpResponse {
  const AuthenticatedHttpResponse({required this.statusCode, required this.body});

  final int statusCode;
  final String body;
}

/// HTTP client that attaches the access token and refreshes once on 401.
class AuthenticatedHttpClient {
  AuthenticatedHttpClient({
    required AuthRepository authRepository,
    required Uri apiOrigin,
    http.Client? client,
  })  : _auth = authRepository,
        _apiOrigin = apiOrigin,
        _client = client ?? http.Client();

  final AuthRepository _auth;
  final Uri _apiOrigin;
  final http.Client _client;

  Uri get apiOrigin => _apiOrigin;

  Future<AuthenticatedHttpResponse> getJsonPath(String path) {
    return _request(method: 'GET', path: path);
  }

  Future<AuthenticatedHttpResponse> postJsonPath(
    String path, {
    String? body,
    Map<String, String>? extraHeaders,
  }) {
    return _request(method: 'POST', path: path, body: body, extraHeaders: extraHeaders);
  }

  Future<AuthenticatedHttpResponse> putJsonPath(String path, {required String body}) {
    return _request(method: 'PUT', path: path, body: body);
  }

  Future<AuthenticatedHttpResponse> patchJsonPath(String path, {required String body}) {
    return _request(method: 'PATCH', path: path, body: body);
  }

  Future<AuthenticatedHttpResponse> postMultipartPath(
    String path, {
    required Map<String, String> fields,
    required Map<String, MultipartFilePayload> files,
  }) async {
    final uri = _resolve(path);
    var access = await _auth.accessToken();
    if (access == null || access.isEmpty) {
      return const AuthenticatedHttpResponse(statusCode: 401, body: '');
    }
    var response = await _multipart(uri, access, fields: fields, files: files);
    if (response.statusCode != 401) {
      return response;
    }
    try {
      final tokens = await _auth.refreshTokens();
      response = await _multipart(uri, tokens.accessToken, fields: fields, files: files);
    } on AuthFailure {
      return const AuthenticatedHttpResponse(statusCode: 401, body: '');
    } on AuthNetworkFailure {
      return response;
    }
    return response;
  }

  Future<AuthenticatedHttpResponse> _multipart(
    Uri uri,
    String accessToken, {
    required Map<String, String> fields,
    required Map<String, MultipartFilePayload> files,
  }) async {
    final request = http.MultipartRequest('POST', uri);
    request.headers['authorization'] = 'Bearer $accessToken';
    request.fields.addAll(fields);
    for (final entry in files.entries) {
      request.files.add(
        http.MultipartFile.fromBytes(
          entry.key,
          entry.value.bytes,
          filename: entry.value.filename,
        ),
      );
    }
    try {
      final streamed = await _client.send(request);
      final body = await streamed.stream.bytesToString();
      return AuthenticatedHttpResponse(statusCode: streamed.statusCode, body: body);
    } catch (_) {
      throw AuthNetworkFailure();
    }
  }

  Future<AuthenticatedHttpResponse> _request({
    required String method,
    required String path,
    String? body,
    Map<String, String>? extraHeaders,
  }) async {
    final uri = _resolve(path);
    return _send(method: method, uri: uri, body: body, extraHeaders: extraHeaders);
  }

  Uri _resolve(String path) {
    final parsed = Uri.parse(path);
    final normalized = parsed.path.startsWith('/') ? parsed.path.substring(1) : parsed.path;
    final segments = [
      ..._apiOrigin.pathSegments.where((s) => s.isNotEmpty),
      ...normalized.split('/').where((s) => s.isNotEmpty),
    ];
    return _apiOrigin.replace(pathSegments: segments, query: parsed.query);
  }

  Future<AuthenticatedHttpResponse> _send({
    required String method,
    required Uri uri,
    String? body,
    Map<String, String>? extraHeaders,
  }) async {
    var access = await _auth.accessToken();
    if (access == null || access.isEmpty) {
      return const AuthenticatedHttpResponse(statusCode: 401, body: '');
    }
    var response = await _dispatch(method, uri, access, body, extraHeaders);
    if (response.statusCode != 401) {
      return response;
    }
    try {
      final tokens = await _auth.refreshTokens();
      response = await _dispatch(method, uri, tokens.accessToken, body, extraHeaders);
    } on AuthFailure {
      return const AuthenticatedHttpResponse(statusCode: 401, body: '');
    } on AuthNetworkFailure {
      return response;
    }
    return response;
  }

  Future<AuthenticatedHttpResponse> _dispatch(
    String method,
    Uri uri,
    String accessToken,
    String? body,
    Map<String, String>? extraHeaders,
  ) async {
    final headers = {
      'authorization': 'Bearer $accessToken',
      if (body != null) 'content-type': 'application/json',
      ...?extraHeaders,
    };
    late http.Response response;
    try {
      switch (method) {
        case 'GET':
          response = await _client.get(uri, headers: headers);
        case 'POST':
          response = await _client.post(uri, headers: headers, body: body ?? '');
        case 'PUT':
          response = await _client.put(uri, headers: headers, body: body);
        case 'PATCH':
          response = await _client.patch(uri, headers: headers, body: body);
        default:
          throw UnsupportedError(method);
      }
    } catch (_) {
      throw AuthNetworkFailure();
    }
    return AuthenticatedHttpResponse(statusCode: response.statusCode, body: response.body);
  }
}
