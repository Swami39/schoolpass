import 'gps_models.dart';
import 'sync_client.dart';

abstract class TransportGpsSyncClient {
  Future<List<TransportGpsSampleSyncResult>> syncBatch({
    required List<TransportGpsSampleRequest> samples,
    required String clientDeviceId,
  });
}

typedef GpsBatchHandler = Future<List<TransportGpsSampleSyncResult>> Function({
  required List<TransportGpsSampleRequest> samples,
  required String clientDeviceId,
});

class FakeTransportGpsSyncClient implements TransportGpsSyncClient {
  FakeTransportGpsSyncClient();

  final List<List<TransportGpsSampleRequest>> batches = [];
  GpsBatchHandler? handler;
  Exception? nextError;

  @override
  Future<List<TransportGpsSampleSyncResult>> syncBatch({
    required List<TransportGpsSampleRequest> samples,
    required String clientDeviceId,
  }) async {
    batches.add(samples);
    if (nextError != null) {
      final err = nextError!;
      nextError = null;
      throw err;
    }
    if (handler == null) {
      throw SyncTransientFailure('no batch handler');
    }
    return handler!(samples: samples, clientDeviceId: clientDeviceId);
  }
}
