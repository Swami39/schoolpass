import '../academic/admin_academic_api.dart';
import '../imports/admin_imports_api.dart';
import '../operations/admin_operations_api.dart';
import '../people/admin_people_api.dart';
import '../auth/auth_api.dart';
import '../auth/auth_repository.dart';
import '../http/authenticated_http_client.dart';
import '../school/admin_school_api.dart';
import '../session/token_store.dart';

class AdminDependencies {
  AdminDependencies({
    required this.apiOrigin,
    this.tenantId,
    required this.tokenStore,
    required this.authApi,
    required this.authRepository,
    required this.http,
  });

  factory AdminDependencies.production({TokenStore? tokenStore}) {
    const origin = String.fromEnvironment('SCHOOLPASS_API_ORIGIN', defaultValue: 'http://127.0.0.1:8000');
    const tenantId = String.fromEnvironment('SCHOOLPASS_TENANT_ID', defaultValue: '');
    final apiOrigin = Uri.parse(origin);
    return AdminDependencies.create(
      apiOrigin: apiOrigin,
      tenantId: tenantId.isEmpty ? null : tenantId,
      tokenStore: tokenStore ?? InMemoryTokenStore(),
    );
  }

  factory AdminDependencies.create({
    required Uri apiOrigin,
    String? tenantId,
    required TokenStore tokenStore,
    AuthApi? authApi,
    AuthRepository? authRepository,
    AuthenticatedHttpClient? httpClient,
  }) {
    final resolvedAuthApi = authApi ?? AuthApi(apiOrigin: apiOrigin);
    final resolvedAuthRepository =
        authRepository ?? AuthRepository(api: resolvedAuthApi, tokenStore: tokenStore);
    final resolvedHttp = httpClient ??
        AuthenticatedHttpClient(
          authRepository: resolvedAuthRepository,
          apiOrigin: apiOrigin,
        );
    return AdminDependencies(
      apiOrigin: apiOrigin,
      tenantId: tenantId,
      tokenStore: tokenStore,
      authApi: resolvedAuthApi,
      authRepository: resolvedAuthRepository,
      http: resolvedHttp,
    );
  }

  final Uri apiOrigin;
  final String? tenantId;
  final TokenStore tokenStore;
  final AuthApi authApi;
  final AuthRepository authRepository;
  final AuthenticatedHttpClient http;

  AdminSchoolApi get schoolApi => AdminSchoolApi(http);

  AdminAcademicApi get academicApi => AdminAcademicApi(http);

  AdminPeopleApi get peopleApi => AdminPeopleApi(http);

  AdminOperationsApi get operationsApi => AdminOperationsApi(http);

  AdminImportsApi get importsApi => AdminImportsApi(http);
}
