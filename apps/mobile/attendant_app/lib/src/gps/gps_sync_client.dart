import 'dart:convert';

import '../http/authenticated_http_client.dart';
import 'gps_models.dart';

/// Syncs buffered GNSS samples to `POST /api/v1/transport/gps/samples/sync`.
///
/// The backend dedupes on `client_sample_id`, so a retried batch is safe.
class HttpGpsSyncClient {
  HttpGpsSyncClient(this._http);

  final AuthenticatedHttpClient _http;

  static const String clientDeviceIdHeader = 'x-client-device-id';

  /// Backend cap per request (`MAX_GPS_BATCH_SIZE`).
  static const int maxBatchSize = 50;

  /// Returns the number of results the server acknowledged.
  Future<int> syncSamples({
    required List<GpsSample> samples,
    required String clientDeviceId,
  }) async {
    if (samples.isEmpty) {
      return 0;
    }
    final response = await _http.postJsonPath(
      'api/v1/transport/gps/samples/sync',
      body: jsonEncode({
        'samples': samples.map((s) => s.toJson()).toList(),
      }),
      extraHeaders: {clientDeviceIdHeader: clientDeviceId},
    );
    if (response.statusCode == 401 || response.statusCode == 403) {
      throw GpsAuthFailure(response.statusCode);
    }
    if (response.statusCode == 404 || response.statusCode == 422) {
      throw GpsPermanentFailure(response.statusCode);
    }
    if (response.statusCode >= 500 || response.statusCode == 0) {
      throw GpsTransientFailure(response.statusCode);
    }
    if (response.statusCode != 200) {
      throw GpsSyncFailure('unexpected status ${response.statusCode}');
    }
    try {
      final decoded = jsonDecode(response.body);
      if (decoded is! Map<String, dynamic> || decoded['results'] is! List) {
        throw const FormatException('malformed gps sync response');
      }
      return (decoded['results'] as List).length;
    } catch (_) {
      throw GpsParseFailure();
    }
  }
}

class GpsSyncFailure implements Exception {
  GpsSyncFailure(this.message);

  final String message;

  @override
  String toString() => 'GpsSyncFailure: $message';
}

class GpsAuthFailure extends GpsSyncFailure {
  GpsAuthFailure(this.statusCode) : super('gps auth failed: $statusCode');

  final int statusCode;
}

class GpsTransientFailure extends GpsSyncFailure {
  GpsTransientFailure(this.statusCode) : super('gps transient failure: $statusCode');

  final int statusCode;
}

class GpsPermanentFailure extends GpsSyncFailure {
  GpsPermanentFailure(this.statusCode) : super('gps samples rejected: $statusCode');

  final int statusCode;
}

class GpsParseFailure extends GpsSyncFailure {
  GpsParseFailure() : super('malformed gps sync response');
}
