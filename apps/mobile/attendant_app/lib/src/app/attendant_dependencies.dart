import '../auth/auth_api.dart';
import '../auth/auth_repository.dart';
import '../http/authenticated_http_client.dart';
import '../nfc/transport_nfc_http_client.dart';
import '../session/token_store.dart';
import '../trips/attendant_trips_api.dart';

class AttendantDependencies {
  AttendantDependencies({
    required this.apiOrigin,
    required this.tokenStore,
    required this.authApi,
    required this.authRepository,
    required this.http,
  });

  factory AttendantDependencies.create({
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
    return AttendantDependencies(
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

  AttendantTripsApi get tripsApi => AttendantTripsApi(http);
  AttendantDeviceApi get deviceApi => AttendantDeviceApi(http);
  HttpTransportNfcSyncClient get nfcSyncClient => HttpTransportNfcSyncClient(http);
}
