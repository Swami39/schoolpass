import 'package:parent_app/src/session/secure_token_store.dart';
import 'package:parent_app/src/session/token_store.dart';

import 'flutter_secure_storage_backend.dart';

/// Production [TokenStore] using platform secure storage.
TokenStore createProductionTokenStore() {
  return SecureTokenStore(backend: FlutterSecureStorageBackend());
}
