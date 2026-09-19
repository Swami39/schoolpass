import 'package:teacher_app/src/session/secure_token_store.dart';
import 'package:teacher_app/src/session/token_store.dart';

import 'flutter_secure_storage_backend.dart';

TokenStore createProductionTokenStore() {
  return SecureTokenStore(backend: FlutterSecureStorageBackend());
}
