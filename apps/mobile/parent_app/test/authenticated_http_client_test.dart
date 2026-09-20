import 'dart:convert';

import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:parent_app/parent_app.dart';
import 'package:parent_app/src/http/authenticated_http_client.dart';

void main() {
  test('401 triggers refresh and retries request', () async {
    final store = InMemoryTokenStore();
    await store.writeTokens(accessToken: 'expired', refreshToken: 'refresh-1');
    var protectedCalls = 0;
    final mock = MockClient((request) async {
      if (request.url.path.endsWith('/refresh')) {
        return http.Response(
          jsonEncode({'access_token': 'fresh', 'refresh_token': 'refresh-2'}),
          200,
        );
      }
      if (request.url.path.endsWith('/parent/children')) {
        protectedCalls += 1;
        final auth = request.headers['authorization'];
        if (auth == 'Bearer expired') {
          return http.Response('unauthorized', 401);
        }
        return http.Response(jsonEncode({'items': []}), 200);
      }
      return http.Response('not found', 404);
    });
    final authApi = AuthApi(apiOrigin: Uri.parse('https://api.example.invalid'), client: mock);
    final authRepository = AuthRepository(api: authApi, tokenStore: store);
    final client = AuthenticatedHttpClient(
      authRepository: authRepository,
      apiOrigin: Uri.parse('https://api.example.invalid'),
      client: mock,
    );
    final response = await client.getJsonPath('/api/v1/parent/children');
    expect(response.statusCode, 200);
    expect(protectedCalls, 2);
    expect(await store.readAccessToken(), 'fresh');
  });

  test('preserves query string on relative API paths', () async {
    final store = InMemoryTokenStore();
    await store.writeTokens(accessToken: 'access', refreshToken: 'refresh-1');
    Uri? seen;
    final mock = MockClient((request) async {
      seen = request.url;
      return http.Response(jsonEncode({'items': []}), 200);
    });
    final client = AuthenticatedHttpClient(
      authRepository: AuthRepository(
        api: AuthApi(apiOrigin: Uri.parse('https://api.example.invalid'), client: mock),
        tokenStore: store,
      ),
      apiOrigin: Uri.parse('https://api.example.invalid'),
      client: mock,
    );
    await client.getJsonPath(
      '/api/v1/parent/children/22222222-2222-4222-8222-222222222222/attendance?from_date=2026-09-01&limit=30',
    );
    expect(seen, isNotNull);
    expect(seen!.path, '/api/v1/parent/children/22222222-2222-4222-8222-222222222222/attendance');
    expect(seen!.queryParameters['from_date'], '2026-09-01');
    expect(seen!.queryParameters['limit'], '30');
  });
}
