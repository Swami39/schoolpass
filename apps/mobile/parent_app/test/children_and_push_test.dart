import 'dart:convert';

import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:parent_app/parent_app.dart';
import 'package:parent_app/src/http/authenticated_http_client.dart';

void main() {
  test('children api parses authorized list', () async {
    final store = InMemoryTokenStore();
    await store.writeTokens(accessToken: 'token', refreshToken: 'refresh');
    final mock = MockClient((request) async {
      return http.Response(
        jsonEncode({
          'items': [
            {
              'id': '11111111-1111-4111-8111-111111111111',
              'first_name': 'Alex',
              'middle_name': null,
              'last_name': 'Rivera',
              'admission_no': 'A-1',
              'status': 'active',
            },
          ],
        }),
        200,
      );
    });
    final deps = ParentDependencies.create(
      apiOrigin: Uri.parse('https://api.example.invalid'),
      tokenStore: store,
      pushProvider: FakePlatformPushProvider(),
      httpClient: AuthenticatedHttpClient(
        authRepository: AuthRepository(
          api: AuthApi(apiOrigin: Uri.parse('https://api.example.invalid'), client: mock),
          tokenStore: store,
        ),
        apiOrigin: Uri.parse('https://api.example.invalid'),
        client: mock,
      ),
    );
    final children = await deps.childrenApi.fetchChildren();
    expect(children, hasLength(1));
    expect(children.first.displayName, 'Alex Rivera');
  });

  test('push registration uses fake provider', () async {
    final store = InMemoryTokenStore();
    await store.writeTokens(accessToken: 'token', refreshToken: 'refresh');
    final provider = FakePlatformPushProvider(token: 'fcm-token-value', permissionGranted: true);
    final mock = MockClient((request) async {
      if (request.url.path.endsWith('/push-devices')) {
        expect(request.headers['authorization'], 'Bearer token');
        final body = jsonDecode(request.body) as Map<String, dynamic>;
        expect(body['platform'], 'android');
        expect(body['fcm_token'], 'fcm-token-value');
        return http.Response('{"id":"d","platform":"android","status":"active"}', 200);
      }
      return http.Response('not found', 404);
    });
    final deps = ParentDependencies.create(
      apiOrigin: Uri.parse('https://api.example.invalid'),
      tokenStore: store,
      pushProvider: provider,
      httpClient: AuthenticatedHttpClient(
        authRepository: AuthRepository(
          api: AuthApi(apiOrigin: Uri.parse('https://api.example.invalid'), client: mock),
          tokenStore: store,
        ),
        apiOrigin: Uri.parse('https://api.example.invalid'),
        client: mock,
      ),
    );
    await deps.pushService.registerDeviceIfNeeded();
    expect(provider.tokenCalls, 1);
  });

  test('push permission denied skips registration', () async {
    final provider = FakePlatformPushProvider(token: null, permissionGranted: false);
    final deps = ParentDependencies.create(
      apiOrigin: Uri.parse('https://api.example.invalid'),
      tokenStore: InMemoryTokenStore(),
      pushProvider: provider,
    );
    await deps.pushService.registerDeviceIfNeeded();
    expect(provider.tokenCalls, 1);
  });
}
