class AttendantUnauthorized implements Exception {}

class AttendantNotFound implements Exception {}

class AttendantRequestFailure implements Exception {
  AttendantRequestFailure(this.statusCode);
  final int statusCode;
}

class AttendantParseFailure implements Exception {}

void throwIfAttendantDenied(int statusCode) {
  if (statusCode == 401 || statusCode == 403) {
    throw AttendantUnauthorized();
  }
  if (statusCode == 404) {
    throw AttendantNotFound();
  }
}
