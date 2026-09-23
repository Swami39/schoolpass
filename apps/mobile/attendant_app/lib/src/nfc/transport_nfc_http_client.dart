import 'dart:convert';

import 'package:attendant_nfc/attendant_nfc.dart';

import '../api/attendant_errors.dart';
import '../http/authenticated_http_client.dart';

class HttpTransportNfcSyncClient implements TransportNfcSyncClient {
  HttpTransportNfcSyncClient(this._http);

  final AuthenticatedHttpClient _http;

  @override
  Future<TransportNfcSyncResponse> syncEvent({
    required TransportNfcSyncRequest request,
    required String clientDeviceId,
  }) async {
    final response = await _http.postJsonPath(
      'api/v1/transport/nfc/events/sync',
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
      throw AttendantParseFailure();
    }
    return TransportNfcSyncResponse.fromJson(decoded);
  }
}

class AttendantDeviceApi {
  AttendantDeviceApi(this._http);

  final AuthenticatedHttpClient _http;

  Future<String> registerDevice(String deviceUuid) async {
    final response = await _http.postJsonPath(
      'api/v1/transport-attendant/client-devices',
      body: jsonEncode({'device_uuid': deviceUuid}),
    );
    throwIfAttendantDenied(response.statusCode);
    if (response.statusCode != 200) {
      throw AttendantRequestFailure(response.statusCode);
    }
    final decoded = jsonDecode(response.body);
    if (decoded is! Map<String, dynamic>) {
      throw AttendantParseFailure();
    }
    return decoded['client_device_id'] as String;
  }
}
