import 'package:parent_transport/parent_transport.dart';

import '../attendance/attendance_api.dart';
import '../auth/auth_api.dart';
import '../auth/auth_repository.dart';
import '../children/children_api.dart';
import '../http/authenticated_http_client.dart';
import '../notifications/notifications_api.dart';
import '../preferences/notification_preferences_api.dart';
import '../push/push_notification_service.dart';
import '../session/token_store.dart';

class ParentDependencies {
  ParentDependencies({
    required this.apiOrigin,
    required this.tokenStore,
    required this.pushProvider,
    required this.authApi,
    required this.authRepository,
    required this.http,
  });

  factory ParentDependencies.create({
    required Uri apiOrigin,
    required TokenStore tokenStore,
    required PlatformPushProvider pushProvider,
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
    return ParentDependencies(
      apiOrigin: apiOrigin,
      tokenStore: tokenStore,
      pushProvider: pushProvider,
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
  final PlatformPushProvider pushProvider;

  ChildrenApi get childrenApi => ChildrenApi(http);
  AttendanceApi get attendanceApi => AttendanceApi(http);
  NotificationsApi get notificationsApi => NotificationsApi(http);
  NotificationPreferencesApi get preferencesApi => NotificationPreferencesApi(http);

  ParentBusLocationApi get busLocationApi => ParentBusLocationApi(
        transport: http,
        apiOrigin: apiOrigin,
      );

  PushNotificationService get pushService => PushNotificationService(
        provider: pushProvider,
        http: http,
      );
}
