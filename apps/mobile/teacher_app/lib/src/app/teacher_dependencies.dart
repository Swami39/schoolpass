import '../auth/auth_api.dart';
import '../auth/auth_repository.dart';
import '../classes/teacher_classes_api.dart';
import '../http/authenticated_http_client.dart';
import '../session/token_store.dart';

class TeacherDependencies {
  TeacherDependencies({
    required this.apiOrigin,
    required this.tokenStore,
    required this.authApi,
    required this.authRepository,
    required this.http,
  });

  factory TeacherDependencies.production({TokenStore? tokenStore}) {
    const origin = String.fromEnvironment('SCHOOLPASS_API_ORIGIN', defaultValue: 'http://localhost:8000');
    final apiOrigin = Uri.parse(origin);
    return TeacherDependencies.create(
      apiOrigin: apiOrigin,
      tokenStore: tokenStore ?? InMemoryTokenStore(),
    );
  }

  factory TeacherDependencies.create({
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
    return TeacherDependencies(
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

  TeacherClassesApi get classesApi => TeacherClassesApi(http);
}
