import 'dart:convert';

import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:parent_app/parent_app.dart';
import 'package:parent_app/src/http/authenticated_http_client.dart';

void main() {
  test('logout resets child selection', () async {
    final store = InMemoryTokenStore();
    final mock = MockClient((request) async {
      if (request.url.path.endsWith('/password/login')) {
        return http.Response(
          jsonEncode({'access_token': 'access', 'refresh_token': 'refresh'}),
          200,
        );
      }
      if (request.url.path.endsWith('/parent/children')) {
        return http.Response(
          jsonEncode({
            'items': [
              {
                'id': '22222222-2222-4222-8222-222222222222',
                'first_name': 'Sam',
                'middle_name': null,
                'last_name': 'Lee',
                'admission_no': 'B-2',
                'status': 'active',
              },
            ],
          }),
          200,
        );
      }
      if (request.url.path.endsWith('/logout')) {
        return http.Response('{"ok":true}', 200);
      }
      return http.Response('not found', 404);
    });
    final deps = ParentDependencies.create(
      apiOrigin: Uri.parse('https://api.example.invalid'),
      tokenStore: store,
      pushProvider: FakePlatformPushProvider(),
      authApi: AuthApi(apiOrigin: Uri.parse('https://api.example.invalid'), client: mock),
      httpClient: AuthenticatedHttpClient(
        authRepository: AuthRepository(
          api: AuthApi(apiOrigin: Uri.parse('https://api.example.invalid'), client: mock),
          tokenStore: store,
        ),
        apiOrigin: Uri.parse('https://api.example.invalid'),
        client: mock,
      ),
    );
    final controller = ParentAppController(deps);
    await controller.login('parent@example.invalid', 'secret');
    expect(controller.selectedChild, isNotNull);
    await controller.logout();
    expect(controller.phase, ParentAppPhase.signedOut);
    expect(controller.selectedChild, isNull);
    expect(controller.children, isEmpty);
  });
}
