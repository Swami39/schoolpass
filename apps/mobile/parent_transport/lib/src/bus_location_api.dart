import 'dart:convert';

import 'bus_location_errors.dart';
import 'bus_location_models.dart';
import 'http_transport.dart';

/// Thin client for parent current bus location (Phase 6D.3).
///
/// Authorization and trip/bus derivation remain on the server. This class only
/// performs GET `/api/v1/parent/children/{student_id}/bus-location`.
class ParentBusLocationApi {
  ParentBusLocationApi({
    required ParentBusLocationHttpTransport transport,
    required Uri apiOrigin,
  })  : _transport = transport,
        _apiOrigin = apiOrigin;

  final ParentBusLocationHttpTransport _transport;
  final Uri _apiOrigin;

  /// Fetches the current bus location for [studentId] (UUID string).
  ///
  /// Does not accept tenant, guardian, trip, bus, or route identifiers.
  Future<ParentBusLocation> fetchChildBusLocation({required String studentId}) async {
    if (studentId.trim().isEmpty) {
      throw ParentBusLocationParseFailure('missing student_id');
    }
    final uri = _childBusLocationUri(studentId);
    final ParentHttpResponse response;
    try {
      response = await _transport.get(uri);
    } on ParentBusLocationNetworkFailure {
      rethrow;
    } catch (_) {
      throw ParentBusLocationNetworkFailure();
    }

    if (response.statusCode == 401 || response.statusCode == 403) {
      throw ParentBusLocationAuthFailure(statusCode: response.statusCode);
    }
    if (response.statusCode == 404) {
      throw ParentBusLocationNotFoundFailure();
    }
    if (response.statusCode != 200) {
      throw ParentBusLocationUnexpectedHttpFailure(statusCode: response.statusCode);
    }

    return _parseBody(response.body);
  }

  Uri childBusLocationUri(String studentId) => _childBusLocationUri(studentId);

  Uri _childBusLocationUri(String studentId) {
    final segments = <String>[
      ..._apiOrigin.pathSegments.where((s) => s.isNotEmpty),
      'api',
      'v1',
      'parent',
      'children',
      studentId,
      'bus-location',
    ];
    return _apiOrigin.replace(pathSegments: segments, query: '');
  }

  ParentBusLocation _parseBody(String body) {
    final Object? decoded;
    try {
      decoded = jsonDecode(body);
    } catch (_) {
      throw ParentBusLocationParseFailure('invalid json');
    }
    if (decoded is! Map<String, dynamic>) {
      throw ParentBusLocationParseFailure('invalid json shape');
    }
    return ParentBusLocation.parseJson(decoded);
  }
}
