import '../session/token_storage_exception.dart';
import '../session/token_store.dart';
import 'auth_api.dart';
import 'auth_models.dart';

/// Session boundary: login, refresh, logout, and token persistence.
class AuthRepository {
  AuthRepository({
    required AuthApi api,
    required TokenStore tokenStore,
  })  : _api = api,
        _tokenStore = tokenStore;

  final AuthApi _api;
  final TokenStore _tokenStore;
  Future<AuthTokens>? _refreshInFlight;

  Future<AuthSession?> loadPersistedSession() async {
    final access = await _tokenStore.readAccessToken();
    final refresh = await _tokenStore.readRefreshToken();
    if (access == null || refresh == null || access.isEmpty || refresh.isEmpty) {
      return null;
    }
    return AuthSession(tokens: AuthTokens(accessToken: access, refreshToken: refresh));
  }

  Future<AuthSession> login({
    required String identifier,
    required String password,
  }) async {
    final tokens = await _api.passwordLogin(identifier: identifier, password: password);
    try {
      await _tokenStore.writeTokens(
        accessToken: tokens.accessToken,
        refreshToken: tokens.refreshToken,
      );
    } on TokenStorageException {
      throw AuthFailure('could not persist session');
    }
    return AuthSession(tokens: tokens);
  }

  Future<void> logout() async {
    final access = await _tokenStore.readAccessToken();
    if (access != null && access.isNotEmpty) {
      try {
        await _api.logout(accessToken: access);
      } catch (_) {
        // Best-effort server logout; local session must still clear.
      }
    }
    await _tokenStore.clear();
  }

  Future<String?> accessToken() => _tokenStore.readAccessToken();

  Future<AuthTokens> refreshTokens() {
    final existing = _refreshInFlight;
    if (existing != null) {
      return existing;
    }
    final future = _refreshTokensOnce();
    _refreshInFlight = future;
    return future.whenComplete(() {
      if (identical(_refreshInFlight, future)) {
        _refreshInFlight = null;
      }
    });
  }

  Future<AuthTokens> _refreshTokensOnce() async {
    final refresh = await _tokenStore.readRefreshToken();
    if (refresh == null || refresh.isEmpty) {
      throw AuthFailure('no refresh token');
    }
    try {
      final tokens = await _api.refresh(refreshToken: refresh);
      try {
        await _tokenStore.writeTokens(
          accessToken: tokens.accessToken,
          refreshToken: tokens.refreshToken,
        );
      } on TokenStorageException {
        throw AuthFailure('could not persist session');
      }
      return tokens;
    } on AuthFailure {
      await _tokenStore.clear();
      rethrow;
    } on AuthNetworkFailure {
      rethrow;
    }
  }
}
