class AuthTokens {
  const AuthTokens({required this.accessToken, required this.refreshToken});

  final String accessToken;
  final String refreshToken;
}

class AuthSession {
  const AuthSession({required this.tokens});

  final AuthTokens tokens;
}

class AuthFailure implements Exception {
  AuthFailure(this.message);
  final String message;
}

class AuthNetworkFailure implements Exception {}

class AuthMfaRequired implements Exception {
  AuthMfaRequired(this.mfaToken);
  final String mfaToken;
}
