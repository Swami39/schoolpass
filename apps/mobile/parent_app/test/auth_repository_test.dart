import 'dart:convert';

import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:parent_app/parent_app.dart';

import 'support/map_secure_storage_backend.dart';

void main() {
  group('AuthRepository', () {
    late InMemoryTokenStore store;
    late AuthApi api;
    late AuthRepository repo;

    setUp(() {
      store = InMemoryTokenStore();
      api = AuthApi(
        apiOrigin: Uri.parse('https://api.example.invalid'),
        client: MockClient((request) async {
          if (request.url.path.endsWith('/password/login')) {
            return http.Response(
              jsonEncode({'access_token': 'access-1', 'refresh_token': 'refresh-1'}),
              200,
            );
          }
          if (request.url.path.endsWith('/refresh')) {
            return http.Response(
              jsonEncode({'access_token': 'access-2', 'refresh_token': 'refresh-2'}),
              200,
            );
          }
          if (request.url.path.endsWith('/logout')) {
            return http.Response('{"ok":true}', 200);
          }
          return http.Response('not found', 404);
        }),
      );
      repo = AuthRepository(api: api, tokenStore: store);
    });

    test('login persists tokens', () async {
      final session = await repo.login(identifier: 'parent@example.invalid', password: 'secret');
      expect(session.tokens.accessToken, 'access-1');
      expect(await store.readAccessToken(), 'access-1');
      expect(await store.readRefreshToken(), 'refresh-1');
    });

    test('logout clears session', () async {
      await repo.login(identifier: 'parent@example.invalid', password: 'secret');
      await repo.logout();
      expect(await store.readAccessToken(), isNull);
    });

    test('refresh updates tokens', () async {
      await store.writeTokens(accessToken: 'old', refreshToken: 'refresh-1');
      final tokens = await repo.refreshTokens();
      expect(tokens.accessToken, 'access-2');
      expect(await store.readAccessToken(), 'access-2');
    });

    test('refresh failure clears store', () async {
      api = AuthApi(
        apiOrigin: Uri.parse('https://api.example.invalid'),
        client: MockClient((request) async => http.Response('unauthorized', 401)),
      );
      repo = AuthRepository(api: api, tokenStore: store);
      await store.writeTokens(accessToken: 'old', refreshToken: 'bad');
      await expectLater(repo.refreshTokens(), throwsA(isA<AuthFailure>()));
      expect(await store.readAccessToken(), isNull);
    });

    test('concurrent refresh shares single flight', () async {
      var refreshCalls = 0;
      api = AuthApi(
        apiOrigin: Uri.parse('https://api.example.invalid'),
        client: MockClient((request) async {
          if (request.url.path.endsWith('/refresh')) {
            refreshCalls += 1;
            await Future<void>.delayed(const Duration(milliseconds: 20));
            return http.Response(
              jsonEncode({'access_token': 'access-3', 'refresh_token': 'refresh-3'}),
              200,
            );
          }
          return http.Response('not found', 404);
        }),
      );
      repo = AuthRepository(api: api, tokenStore: store);
      await store.writeTokens(accessToken: 'old', refreshToken: 'refresh-1');
      final results = await Future.wait([repo.refreshTokens(), repo.refreshTokens()]);
      expect(refreshCalls, 1);
      expect(results.first.accessToken, 'access-3');
    });

    test('network failure on refresh does not clear stored session', () async {
      api = AuthApi(
        apiOrigin: Uri.parse('https://api.example.invalid'),
        client: MockClient((request) async => http.Response('server error', 503)),
      );
      repo = AuthRepository(api: api, tokenStore: store);
      await store.writeTokens(accessToken: 'old', refreshToken: 'refresh-1');
      await expectLater(repo.refreshTokens(), throwsA(isA<AuthNetworkFailure>()));
      expect(await store.readAccessToken(), 'old');
      expect(await store.readRefreshToken(), 'refresh-1');
    });

    test('login uses TokenStore for persistence via SecureTokenStore', () async {
      final backend = MapSecureStorageBackend();
      final secureStore = SecureTokenStore(backend: backend);
      repo = AuthRepository(api: api, tokenStore: secureStore);
      await repo.login(identifier: 'parent@example.invalid', password: 'secret');
      expect(backend.values[SecureTokenStore.accessTokenKey], 'access-1');
      expect(backend.values[SecureTokenStore.refreshTokenKey], 'refresh-1');
      await repo.logout();
      expect(backend.values, isEmpty);
    });

    test('storage failure on login surfaces auth failure without persisting', () async {
      final backend = MapSecureStorageBackend();
      backend.failWrites = true;
      repo = AuthRepository(api: api, tokenStore: SecureTokenStore(backend: backend));
      await expectLater(
        repo.login(identifier: 'parent@example.invalid', password: 'secret'),
        throwsA(isA<AuthFailure>()),
      );
      expect(backend.values, isEmpty);
    });

    test('malformed auth response fails', () async {
      api = AuthApi(
        apiOrigin: Uri.parse('https://api.example.invalid'),
        client: MockClient((request) async => http.Response('{"access_token":"only"}', 200)),
      );
      repo = AuthRepository(api: api, tokenStore: store);
      await expectLater(
        repo.login(identifier: 'x', password: 'y'),
        throwsA(isA<AuthFailure>()),
      );
    });
  });
}
