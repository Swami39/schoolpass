import 'dart:io' show Platform;

import 'package:parent_app/src/session/secure_token_store.dart';
import 'package:parent_app/src/session/token_store.dart';

import 'flutter_secure_storage_backend.dart';

/// Production token store: Keystore/Keychain on mobile; in-memory on local macOS runners.
TokenStore createProductionTokenStore() {
  // Local macOS Flutter runners are unsigned and cannot use Data Protection Keychain
  // without Keychain Sharing / provisioning. Keep Keystore/Keychain on mobile.
  if (Platform.isMacOS) {
    return InMemoryTokenStore();
  }
  return SecureTokenStore(backend: FlutterSecureStorageBackend());
}
