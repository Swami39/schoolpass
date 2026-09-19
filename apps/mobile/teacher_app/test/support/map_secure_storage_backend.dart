import 'package:teacher_app/src/session/secure_storage_backend.dart';

/// In-test backend for [SecureTokenStore]; not a stand-in for Keychain/Keystore.
class MapSecureStorageBackend implements SecureStorageBackend {
  final Map<String, String> values = {};
  bool failReads = false;
  bool failWrites = false;
  bool failDeletes = false;

  @override
  Future<String?> read(String key) async {
    if (failReads) {
      throw StateError('read failed');
    }
    return values[key];
  }

  @override
  Future<void> write(String key, String value) async {
    if (failWrites) {
      throw StateError('write failed');
    }
    values[key] = value;
  }

  @override
  Future<void> delete(String key) async {
    if (failDeletes) {
      throw StateError('delete failed');
    }
    values.remove(key);
  }
}
