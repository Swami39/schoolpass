import 'dart:convert';

import 'package:attendant_nfc/attendant_nfc.dart';

import '../api/teacher_errors.dart';
import '../http/authenticated_http_client.dart';

class HttpTeacherClassNfcSyncClient implements TeacherClassNfcSyncClient {
  HttpTeacherClassNfcSyncClient(this._http);

  final AuthenticatedHttpClient _http;

  @override
  Future<TeacherClassNfcSyncResponse> syncEvent({
    required TeacherClassNfcSyncRequest request,
    required String clientDeviceId,
  }) async {
    final response = await _http.postJsonPath(
      '/api/v1/teacher/nfc/events/sync',
      body: jsonEncode(request.toJson()),
      extraHeaders: {kClientDeviceIdHeader: clientDeviceId},
    );
    if (response.statusCode == 401 || response.statusCode == 403) {
      throw SyncAuthConfigurationFailure('auth', statusCode: response.statusCode);
    }
    if (response.statusCode == 404 || response.statusCode == 422) {
      throw SyncPermanentHttpFailure('rejected', statusCode: response.statusCode);
    }
    if (response.statusCode >= 500 || response.statusCode == 0) {
      throw SyncTransientFailure('server', statusCode: response.statusCode);
    }
    if (response.statusCode != 200) {
      throw SyncPermanentHttpFailure('http', statusCode: response.statusCode);
    }
    final decoded = jsonDecode(response.body);
    if (decoded is! Map<String, dynamic>) {
      throw TeacherParseFailure();
    }
    return TeacherClassNfcSyncResponse.fromJson(decoded);
  }
}

class TeacherDeviceApi {
  TeacherDeviceApi(this._http);

  final AuthenticatedHttpClient _http;

  Future<String> registerDevice(String deviceUuid) async {
    final response = await _http.postJsonPath(
      '/api/v1/teacher/client-devices',
      body: jsonEncode({'device_uuid': deviceUuid}),
    );
    throwIfTeacherDenied(response.statusCode);
    if (response.statusCode != 200) {
      throw TeacherRequestFailure(response.statusCode);
    }
    final decoded = jsonDecode(response.body);
    if (decoded is! Map<String, dynamic>) {
      throw TeacherParseFailure();
    }
    return decoded['client_device_id'] as String;
  }
}
