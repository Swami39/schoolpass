import 'package:flutter_test/flutter_test.dart';
import 'package:teacher_app/src/session/secure_token_store.dart';
import 'package:teacher_app/src/session/token_storage_exception.dart';

import 'support/map_secure_storage_backend.dart';

void main() {
  group('SecureTokenStore', () {
    late MapSecureStorageBackend backend;
    late SecureTokenStore store;

    setUp(() {
      backend = MapSecureStorageBackend();
      store = SecureTokenStore(backend: backend);
    });

    test('read returns null when empty', () async {
      expect(await store.readAccessToken(), isNull);
      expect(await store.readRefreshToken(), isNull);
    });

    test('write and read tokens', () async {
      await store.writeTokens(accessToken: 'access-a', refreshToken: 'refresh-b');
      expect(await store.readAccessToken(), 'access-a');
      expect(await store.readRefreshToken(), 'refresh-b');
    });

    test('overwrite updates stored values', () async {
      await store.writeTokens(accessToken: 'access-1', refreshToken: 'refresh-1');
      await store.writeTokens(accessToken: 'access-2', refreshToken: 'refresh-2');
      expect(await store.readAccessToken(), 'access-2');
      expect(await store.readRefreshToken(), 'refresh-2');
    });

    test('clear removes credentials', () async {
      await store.writeTokens(accessToken: 'access-a', refreshToken: 'refresh-b');
      await store.clear();
      expect(await store.readAccessToken(), isNull);
      expect(await store.readRefreshToken(), isNull);
      expect(backend.values, isEmpty);
    });

    test('read failure returns null without throwing', () async {
      backend.failReads = true;
      expect(await store.readAccessToken(), isNull);
    });

    test('write failure throws TokenStorageException and clears partial write', () async {
      backend.failWrites = true;
      await expectLater(
        store.writeTokens(accessToken: 'access-a', refreshToken: 'refresh-b'),
        throwsA(isA<TokenStorageException>()),
      );
      backend.failWrites = false;
      expect(await store.readAccessToken(), isNull);
      expect(await store.readRefreshToken(), isNull);
    });

    test('clear tolerates delete failures', () async {
      await store.writeTokens(accessToken: 'access-a', refreshToken: 'refresh-b');
      backend.failDeletes = true;
      await store.clear();
      backend.failDeletes = false;
      expect(await store.readAccessToken(), 'access-a');
    });
  });
}
