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
  test('fetchStudents parses list response', () async {
    final deps = _depsWithClient((request) async {
      if (request.url.path.endsWith('/api/v1/admin/students')) {
        return http.Response(
          jsonEncode({
            'items': [
              {
                'id': '22222222-2222-2222-2222-222222222222',
                'admission_no': 'A-1',
                'first_name': 'Ada',
                'last_name': 'Lovelace',
                'status': 'active',
              },
            ],
            'next_cursor': null,
          }),
          200,
        );
      }
      return http.Response('not found', 404);
    });
    final students = await deps.peopleApi.fetchStudents();
    expect(students.length, 1);
    expect(students.first.displayName, 'Ada Lovelace');
  });

  test('createStudent surfaces API failure', () async {
    final deps = _depsWithClient((request) async {
      if (request.method == 'POST' && request.url.path.endsWith('/api/v1/admin/students')) {
        return http.Response(jsonEncode({'detail': 'Admission number taken'}), 409);
      }
      return http.Response('not found', 404);
    });
    expect(
      () => deps.peopleApi.createStudent({
        'admission_no': 'X',
        'first_name': 'A',
        'last_name': 'B',
      }),
      throwsA(isA<Exception>()),
    );
  });

  test('createStudent succeeds', () async {
    final deps = _depsWithClient((request) async {
      if (request.method == 'POST' && request.url.path.endsWith('/api/v1/admin/students')) {
        return http.Response(
          jsonEncode({
            'id': '33333333-3333-3333-3333-333333333333',
            'admission_no': 'A-2',
            'first_name': 'Grace',
            'last_name': 'Hopper',
            'status': 'active',
          }),
          200,
        );
      }
      return http.Response('not found', 404);
    });
    final student = await deps.peopleApi.createStudent({
      'admission_no': 'A-2',
      'first_name': 'Grace',
      'last_name': 'Hopper',
    });
    expect(student.admissionNo, 'A-2');
  });
}

AdminDependencies _depsWithClient(Future<http.Response> Function(http.Request) handler) {
  final client = MockClient(handler);
  final store = InMemoryTokenStore();
  store.writeTokens(accessToken: 'access', refreshToken: 'refresh');
  final authApi = AuthApi(apiOrigin: Uri.parse('http://test'));
  final authRepo = AuthRepository(api: authApi, tokenStore: store);
  return AdminDependencies.create(
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
}
