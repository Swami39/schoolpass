import 'dart:convert';

import 'package:admin_app/src/app/admin_app_controller.dart';
import 'package:admin_app/src/app/admin_dependencies.dart';
import 'package:admin_app/src/auth/auth_api.dart';
import 'package:admin_app/src/auth/auth_models.dart';
import 'package:admin_app/src/auth/auth_repository.dart';
import 'package:admin_app/src/http/authenticated_http_client.dart';
import 'package:admin_app/src/session/token_store.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

class _FakeAuthApi extends AuthApi {
  _FakeAuthApi() : super(apiOrigin: Uri.parse('http://test'));

  @override
  Future<AuthTokens> passwordLogin({
    required String identifier,
    required String password,
  }) async {
    return const AuthTokens(accessToken: 'access', refreshToken: 'refresh');
  }

  @override
  Future<AuthTokens> refresh({required String refreshToken}) async {
    throw AuthFailure('expired');
  }
}

void main() {
  test('loads school profile successfully', () async {
    final client = MockClient((request) async {
      if (request.url.path.endsWith('/api/v1/admin/school') && request.method == 'GET') {
        return http.Response(
          jsonEncode({
            'id': '11111111-1111-1111-1111-111111111111',
            'legal_name': 'North Test School',
            'display_name': null,
            'slug': 'north',
            'status': 'active',
            'timezone': 'Asia/Kolkata',
            'country': 'IN',
            'contact_email': null,
            'contact_phone': null,
            'address_line1': null,
            'city': null,
            'state': null,
            'postal_code': null,
            'logo_file_id': null,
          }),
          200,
        );
      }
      return http.Response('not found', 404);
    });
    final store = InMemoryTokenStore();
    await store.writeTokens(accessToken: 'access', refreshToken: 'refresh');
    final deps = AdminDependencies.create(
      apiOrigin: Uri.parse('http://test'),
      tokenStore: store,
      authApi: _FakeAuthApi(),
      authRepository: AuthRepository(api: _FakeAuthApi(), tokenStore: store),
      httpClient: AuthenticatedHttpClient(
        authRepository: AuthRepository(api: _FakeAuthApi(), tokenStore: store),
        apiOrigin: Uri.parse('http://test'),
        client: client,
      ),
    );
    final controller = AdminAppController(deps);
    await controller.loadSchoolProfile();
    expect(controller.schoolProfile?.legalName, 'North Test School');
    expect(controller.errorMessage, isNull);
  });

  test('updates school profile successfully', () async {
    final client = MockClient((request) async {
      if (request.method == 'PATCH' && request.url.path.endsWith('/api/v1/admin/school')) {
        final body = jsonDecode(request.body) as Map<String, dynamic>;
        return http.Response(
          jsonEncode({
            'id': '11111111-1111-1111-1111-111111111111',
            'legal_name': body['legal_name'],
            'display_name': body['display_name'],
            'slug': 'north',
            'status': 'active',
            'timezone': 'Asia/Kolkata',
            'country': 'IN',
            'contact_email': null,
            'contact_phone': null,
            'address_line1': null,
            'city': null,
            'state': null,
            'postal_code': null,
            'logo_file_id': null,
          }),
          200,
        );
      }
      return http.Response('not found', 404);
    });
    final store = InMemoryTokenStore();
    await store.writeTokens(accessToken: 'access', refreshToken: 'refresh');
    final auth = _FakeAuthApi();
    final deps = AdminDependencies.create(
      apiOrigin: Uri.parse('http://test'),
      tokenStore: store,
      authApi: auth,
      authRepository: AuthRepository(api: auth, tokenStore: store),
      httpClient: AuthenticatedHttpClient(
        authRepository: AuthRepository(api: auth, tokenStore: store),
        apiOrigin: Uri.parse('http://test'),
        client: client,
      ),
    );
    final controller = AdminAppController(deps);
    controller.schoolProfile = null;
    final ok = await controller.saveSchoolProfile(
      legalName: 'Updated School',
      displayName: 'Updated',
      timezone: 'Asia/Kolkata',
      country: 'IN',
    );
    expect(ok, isTrue);
    expect(controller.schoolProfile?.legalName, 'Updated School');
    expect(controller.successMessage, isNotNull);
  });

  test('surfaces API error state', () async {
    final client = MockClient((request) async => http.Response('error', 500));
    final store = InMemoryTokenStore();
    await store.writeTokens(accessToken: 'access', refreshToken: 'refresh');
    final auth = _FakeAuthApi();
    final deps = AdminDependencies.create(
      apiOrigin: Uri.parse('http://test'),
      tokenStore: store,
      authApi: auth,
      authRepository: AuthRepository(api: auth, tokenStore: store),
      httpClient: AuthenticatedHttpClient(
        authRepository: AuthRepository(api: auth, tokenStore: store),
        apiOrigin: Uri.parse('http://test'),
        client: client,
      ),
    );
    final controller = AdminAppController(deps);
    await controller.loadSchoolProfile();
    expect(controller.schoolProfile, isNull);
    expect(controller.errorMessage, isNotNull);
  });

  test('authentication failure clears session', () async {
    final client = MockClient((request) async => http.Response('unauthorized', 401));
    final store = InMemoryTokenStore();
    await store.writeTokens(accessToken: 'access', refreshToken: 'refresh');
    final auth = _FakeAuthApi();
    final deps = AdminDependencies.create(
      apiOrigin: Uri.parse('http://test'),
      tokenStore: store,
      authApi: auth,
      authRepository: AuthRepository(api: auth, tokenStore: store),
      httpClient: AuthenticatedHttpClient(
        authRepository: AuthRepository(api: auth, tokenStore: store),
        apiOrigin: Uri.parse('http://test'),
        client: client,
      ),
    );
    final controller = AdminAppController(deps);
    controller.phase = AdminAppPhase.signedIn;
    await controller.loadSchoolProfile();
    expect(controller.phase, AdminAppPhase.signedOut);
    expect(await store.readAccessToken(), isNull);
  });
}
