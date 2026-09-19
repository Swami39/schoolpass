import 'models.dart';

/// Header required by the SchoolPass NFC sync API.
const kClientDeviceIdHeader = 'X-Client-Device-Id';

class SyncTransientFailure implements Exception {
  SyncTransientFailure(this.message, {this.statusCode});

  final String message;
  final int? statusCode;

  @override
  String toString() => message;
}

class SyncAuthConfigurationFailure implements Exception {
  SyncAuthConfigurationFailure(this.message, {required this.statusCode});

  final String message;
  final int statusCode;

  @override
  String toString() => message;
}

class SyncPermanentHttpFailure implements Exception {
  SyncPermanentHttpFailure(this.message, {required this.statusCode});

  final String message;
  final int statusCode;

  @override
  String toString() => message;
}

abstract class TransportNfcSyncClient {
  Future<TransportNfcSyncResponse> syncEvent({
    required TransportNfcSyncRequest request,
    required String clientDeviceId,
  });
}

typedef SyncClientCall = Future<TransportNfcSyncResponse> Function({
  required TransportNfcSyncRequest request,
  required String clientDeviceId,
});

/// In-memory fake for unit tests (no simulated success unless configured).
class FakeTransportNfcSyncClient implements TransportNfcSyncClient {
  FakeTransportNfcSyncClient();

  final List<TransportNfcSyncRequest> calls = [];
  SyncClientCall? handler;
  Exception? nextError;

  @override
  Future<TransportNfcSyncResponse> syncEvent({
    required TransportNfcSyncRequest request,
    required String clientDeviceId,
  }) async {
    calls.add(request);
    if (nextError != null) {
      final err = nextError!;
      nextError = null;
      throw err;
    }
    if (handler == null) {
      throw SyncTransientFailure('no handler configured');
    }
    return handler!(request: request, clientDeviceId: clientDeviceId);
  }
}
