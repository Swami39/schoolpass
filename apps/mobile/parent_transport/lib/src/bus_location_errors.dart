/// Failures surfaced by [ParentBusLocationApi] (domain/transport layer).
class ParentBusLocationNetworkFailure implements Exception {
  ParentBusLocationNetworkFailure([this.cause]);

  final Object? cause;

  @override
  String toString() => 'ParentBusLocationNetworkFailure';
}

class ParentBusLocationAuthFailure implements Exception {
  ParentBusLocationAuthFailure({required this.statusCode});

  final int statusCode;

  @override
  String toString() => 'ParentBusLocationAuthFailure($statusCode)';
}

class ParentBusLocationNotFoundFailure implements Exception {
  ParentBusLocationNotFoundFailure();

  @override
  String toString() => 'ParentBusLocationNotFoundFailure';
}

class ParentBusLocationParseFailure implements Exception {
  ParentBusLocationParseFailure(this.reason);

  final String reason;

  @override
  String toString() => 'ParentBusLocationParseFailure';
}

class ParentBusLocationUnexpectedHttpFailure implements Exception {
  ParentBusLocationUnexpectedHttpFailure({required this.statusCode});

  final int statusCode;

  @override
  String toString() => 'ParentBusLocationUnexpectedHttpFailure($statusCode)';
}
