import 'sync_client.dart';
import 'teacher_models.dart';

abstract class TeacherClassNfcSyncClient {
  Future<TeacherClassNfcSyncResponse> syncEvent({
    required TeacherClassNfcSyncRequest request,
    required String clientDeviceId,
  });
}

typedef TeacherSyncClientCall = Future<TeacherClassNfcSyncResponse> Function({
  required TeacherClassNfcSyncRequest request,
  required String clientDeviceId,
});

class FakeTeacherClassNfcSyncClient implements TeacherClassNfcSyncClient {
  FakeTeacherClassNfcSyncClient();

  final List<TeacherClassNfcSyncRequest> calls = [];
  TeacherSyncClientCall? handler;
  Exception? nextError;

  @override
  Future<TeacherClassNfcSyncResponse> syncEvent({
    required TeacherClassNfcSyncRequest request,
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
