/// Secure persistence for auth tokens (production uses platform secure storage).
abstract class TokenStore {
  Future<String?> readAccessToken();
  Future<String?> readRefreshToken();
  Future<void> writeTokens({required String accessToken, required String refreshToken});
  Future<void> clear();
}

class InMemoryTokenStore implements TokenStore {
  String? _access;
  String? _refresh;

  @override
  Future<String?> readAccessToken() async => _access;

  @override
  Future<String?> readRefreshToken() async => _refresh;

  @override
  Future<void> writeTokens({
    required String accessToken,
    required String refreshToken,
  }) async {
    _access = accessToken;
    _refresh = refreshToken;
  }

  @override
  Future<void> clear() async {
    _access = null;
    _refresh = null;
  }
}
