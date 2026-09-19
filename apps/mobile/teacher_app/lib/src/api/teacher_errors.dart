class TeacherUnauthorized implements Exception {}

class TeacherNotFound implements Exception {}

class TeacherRequestFailure implements Exception {
  TeacherRequestFailure(this.statusCode);
  final int statusCode;
}

class TeacherParseFailure implements Exception {}

void throwIfTeacherDenied(int statusCode) {
  if (statusCode == 401 || statusCode == 403) {
    throw TeacherUnauthorized();
  }
  if (statusCode == 404) {
    throw TeacherNotFound();
  }
}
