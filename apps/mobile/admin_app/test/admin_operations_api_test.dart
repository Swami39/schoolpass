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
  test('fetchCards parses list', () async {
    final client = MockClient((request) async {
      if (request.url.path.endsWith('/api/v1/admin/cards')) {
        return http.Response(
          jsonEncode({
            'items': [
              {'id': '11111111-1111-1111-1111-111111111111', 'status': 'inventory', 'hf_uid': '04ABC'},
            ],
            'next_cursor': null,
          }),
          200,
        );
      }
      return http.Response('not found', 404);
    });
    final store = InMemoryTokenStore();
    await store.writeTokens(accessToken: 'access', refreshToken: 'refresh');
    final authApi = AuthApi(apiOrigin: Uri.parse('http://test'));
    final authRepo = AuthRepository(api: authApi, tokenStore: store);
    final deps = AdminDependencies.create(
      apiOrigin: Uri.parse('http://test'),
      tokenStore: store,
      authApi: authApi,
      authRepository: authRepo,
      httpClient: AuthenticatedHttpClient(
        authRepository: authRepo,
        apiOrigin: Uri.parse('http://test'),
        client: client,
      ),
    );
    final cards = await deps.operationsApi.fetchCards();
    expect(cards.single.hfUid, '04ABC');
  });
}
