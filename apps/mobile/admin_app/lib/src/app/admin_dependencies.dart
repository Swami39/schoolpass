import '../academic/admin_academic_api.dart';
import '../auth/auth_api.dart';
import '../auth/auth_repository.dart';
import '../http/authenticated_http_client.dart';
import '../school/admin_school_api.dart';
import '../session/token_store.dart';

class AdminDependencies {
  AdminDependencies({
    required this.apiOrigin,
    required this.tokenStore,
    required this.authApi,
    required this.authRepository,
    required this.http,
  });

  factory AdminDependencies.production({TokenStore? tokenStore}) {
    const origin = String.fromEnvironment('SCHOOLPASS_API_ORIGIN', defaultValue: 'http://localhost:8000');
    final apiOrigin = Uri.parse(origin);
    return AdminDependencies.create(
      apiOrigin: apiOrigin,
      tokenStore: tokenStore ?? InMemoryTokenStore(),
    );
  }

  factory AdminDependencies.create({
    required Uri apiOrigin,
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
      tokenStore: tokenStore,
      authApi: resolvedAuthApi,
      authRepository: resolvedAuthRepository,
      http: resolvedHttp,
    );
  }

  final Uri apiOrigin;
  final TokenStore tokenStore;
  final AuthApi authApi;
  final AuthRepository authRepository;
  final AuthenticatedHttpClient http;

  AdminSchoolApi get schoolApi => AdminSchoolApi(http);

  AdminAcademicApi get academicApi => AdminAcademicApi(http);
}
