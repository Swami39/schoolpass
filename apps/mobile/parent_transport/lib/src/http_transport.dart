import 'bus_location_errors.dart';

/// HTTP response from the app-owned authenticated transport.
class ParentHttpResponse {
  const ParentHttpResponse({required this.statusCode, required this.body});

  final int statusCode;
  final String body;
}

/// Authenticated GET; JWT and refresh are applied by the app layer, not by
/// [ParentBusLocationApi].
abstract class ParentBusLocationHttpTransport {
  Future<ParentHttpResponse> get(Uri uri);
}

/// Records the last request for unit tests.
class FakeParentBusLocationHttpTransport implements ParentBusLocationHttpTransport {
  FakeParentBusLocationHttpTransport();

  Uri? lastUri;
  Object? nextError;
  Future<ParentHttpResponse> Function(Uri uri)? handler;

  @override
  Future<ParentHttpResponse> get(Uri uri) async {
    lastUri = uri;
    if (nextError != null) {
      final err = nextError!;
      nextError = null;
      Error.throwWithStackTrace(err, StackTrace.current);
    }
    final fn = handler;
    if (fn == null) {
      throw ParentBusLocationNetworkFailure('no handler configured');
    }
    return fn(uri);
  }
}
