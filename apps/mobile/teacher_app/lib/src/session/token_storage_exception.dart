/// Token persistence failed; message intentionally omits secret values.
class TokenStorageException implements Exception {
  TokenStorageException([this.message = 'secure token storage unavailable']);

  final String message;

  @override
  String toString() => 'TokenStorageException: $message';
}
