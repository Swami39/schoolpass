import 'secure_storage_backend.dart';
import 'token_storage_exception.dart';
import 'token_store.dart';

/// Production [TokenStore] backed by platform secure storage.
class SecureTokenStore implements TokenStore {
  SecureTokenStore({required SecureStorageBackend backend}) : _backend = backend;

  static const String accessTokenKey = 'schoolpass.admin.access_token';
  static const String refreshTokenKey = 'schoolpass.admin.refresh_token';

  final SecureStorageBackend _backend;

  @override
  Future<String?> readAccessToken() async {
    try {
      final value = await _backend.read(accessTokenKey);
      if (value == null || value.isEmpty) {
        return null;
      }
      return value;
    } catch (_) {
      return null;
    }
  }

  @override
  Future<String?> readRefreshToken() async {
    try {
      final value = await _backend.read(refreshTokenKey);
      if (value == null || value.isEmpty) {
        return null;
      }
      return value;
    } catch (_) {
      return null;
    }
  }

  @override
  Future<void> writeTokens({
    required String accessToken,
    required String refreshToken,
  }) async {
    try {
      await _backend.write(accessTokenKey, accessToken);
      await _backend.write(refreshTokenKey, refreshToken);
    } catch (_) {
      await _bestEffortClear();
      throw TokenStorageException();
    }
  }

  @override
  Future<void> clear() async {
    await _bestEffortClear();
  }

  Future<void> _bestEffortClear() async {
    try {
      await _backend.delete(accessTokenKey);
    } catch (_) {}
    try {
      await _backend.delete(refreshTokenKey);
    } catch (_) {}
  }
}
