import 'dart:convert';

import 'package:admin_app/src/app/admin_dependencies.dart';
import 'package:admin_app/src/auth/auth_api.dart';
import 'package:admin_app/src/auth/auth_repository.dart';
import 'package:admin_app/src/http/authenticated_http_client.dart';
import 'package:admin_app/src/session/token_store.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

void main() {
  test('parses academic year list', () async {
    final client = MockClient((request) async {
      return http.Response(
        jsonEncode({
          'items': [
            {
              'id': '11111111-1111-1111-1111-111111111111',
              'code': '2025-26',
              'name': 'Year',
              'starts_on': '2025-04-01',
              'ends_on': '2026-03-31',
              'status': 'active',
              'created_at': '2025-01-01T00:00:00Z',
              'updated_at': '2025-01-01T00:00:00Z',
            },
          ],
        }),
        200,
      );
    });
    final store = InMemoryTokenStore();
    await store.writeTokens(accessToken: 'access', refreshToken: 'refresh');
    final auth = AuthApi(apiOrigin: Uri.parse('http://test'));
    final deps = AdminDependencies.create(
      apiOrigin: Uri.parse('http://test'),
      tokenStore: store,
      authRepository: AuthRepository(api: auth, tokenStore: store),
      httpClient: AuthenticatedHttpClient(
        authRepository: AuthRepository(api: auth, tokenStore: store),
        apiOrigin: Uri.parse('http://test'),
        client: client,
      ),
    );
    final years = await deps.academicApi.fetchAcademicYears();
    expect(years.single.code, '2025-26');
  });

  test('passes class_id when loading sections', () async {
    String? requestedPath;
    final client = MockClient((request) async {
      requestedPath = request.url.path + (request.url.hasQuery ? '?${request.url.query}' : '');
      return http.Response(jsonEncode({'items': []}), 200);
    });
    final store = InMemoryTokenStore();
    await store.writeTokens(accessToken: 'access', refreshToken: 'refresh');
    final auth = AuthApi(apiOrigin: Uri.parse('http://test'));
    final deps = AdminDependencies.create(
      apiOrigin: Uri.parse('http://test'),
      tokenStore: store,
      authRepository: AuthRepository(api: auth, tokenStore: store),
      httpClient: AuthenticatedHttpClient(
        authRepository: AuthRepository(api: auth, tokenStore: store),
        apiOrigin: Uri.parse('http://test'),
        client: client,
      ),
    );
    await deps.academicApi.fetchSections(classId: '22222222-2222-2222-2222-222222222222');
    expect(requestedPath, contains('class_id=22222222-2222-2222-2222-222222222222'));
  });
}
