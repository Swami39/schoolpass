import 'dart:convert';

import '../http/authenticated_http_client.dart';
import 'people_models.dart';

class AdminPeopleApiFailure implements Exception {
  AdminPeopleApiFailure(this.message);
  final String message;
}

class AdminPeopleUnauthorized implements Exception {}

class AdminPeopleApi {
  AdminPeopleApi(this._http);

  final AuthenticatedHttpClient _http;

  Future<List<StaffListItem>> fetchStaff({String? search, String? staffType, int? limit}) async {
    final query = <String, String>{};
    if (search != null && search.isNotEmpty) query['search'] = search;
    if (staffType != null && staffType.isNotEmpty) query['staff_type'] = staffType;
    if (limit != null) query['limit'] = limit.toString();
    return _list(_path('api/v1/admin/staff', query), StaffListItem.fromJson);
  }

  Future<StaffDetail> fetchStaffMember(String staffId) => _getObject('api/v1/admin/staff/$staffId', StaffDetail.fromJson);

  Future<StaffDetail> createStaff(Map<String, dynamic> body) =>
      _mutate('POST', 'api/v1/admin/staff', body, StaffDetail.fromJson);

  Future<StaffDetail> updateStaff(String staffId, Map<String, dynamic> body) =>
      _mutate('PATCH', 'api/v1/admin/staff/$staffId', body, StaffDetail.fromJson);

  Future<List<StudentDetail>> fetchStudents({String? search, String? status, int? limit}) async {
    final query = <String, String>{};
    if (search != null && search.isNotEmpty) query['search'] = search;
    if (status != null && status.isNotEmpty) query['status'] = status;
    if (limit != null) query['limit'] = limit.toString();
    return _list(_path('api/v1/admin/students', query), StudentDetail.fromJson);
  }

  Future<StudentDetail> fetchStudent(String studentId) =>
      _getObject('api/v1/admin/students/$studentId', StudentDetail.fromJson);

  Future<StudentDetail> createStudent(Map<String, dynamic> body) =>
      _mutate('POST', 'api/v1/admin/students', body, StudentDetail.fromJson);

  Future<StudentDetail> updateStudent(String studentId, Map<String, dynamic> body) =>
      _mutate('PATCH', 'api/v1/admin/students/$studentId', body, StudentDetail.fromJson);

  Future<List<GuardianDetail>> fetchGuardians({int? limit}) {
    final query = <String, String>{};
    if (limit != null) query['limit'] = limit.toString();
    return _list(_path('api/v1/admin/guardians', query), GuardianDetail.fromJson);
  }

  Future<GuardianDetail> fetchGuardian(String guardianId) =>
      _getObject('api/v1/admin/guardians/$guardianId', GuardianDetail.fromJson);

  Future<GuardianDetail> createGuardian(Map<String, dynamic> body) =>
      _mutate('POST', 'api/v1/admin/guardians', body, GuardianDetail.fromJson);

  Future<GuardianDetail> updateGuardian(String guardianId, Map<String, dynamic> body) =>
      _mutate('PATCH', 'api/v1/admin/guardians/$guardianId', body, GuardianDetail.fromJson);

  Future<List<EnrollmentDetail>> fetchEnrollments({String? sectionId, String? status, int? limit}) {
    final query = <String, String>{};
    if (sectionId != null && sectionId.isNotEmpty) query['section_id'] = sectionId;
    if (status != null && status.isNotEmpty) query['status'] = status;
    if (limit != null) query['limit'] = limit.toString();
    return _list(_path('api/v1/admin/enrollments', query), EnrollmentDetail.fromJson);
  }

  Future<List<EnrollmentDetail>> fetchStudentEnrollments(String studentId) =>
      _list('api/v1/admin/students/$studentId/enrollments', EnrollmentDetail.fromJson);

  Future<EnrollmentDetail> createEnrollment(Map<String, dynamic> body) =>
      _mutate('POST', 'api/v1/admin/enrollments', body, EnrollmentDetail.fromJson);

  Future<EnrollmentDetail> updateEnrollment(String enrollmentId, Map<String, dynamic> body) =>
      _mutate('PATCH', 'api/v1/admin/enrollments/$enrollmentId', body, EnrollmentDetail.fromJson);

  Future<EnrollmentDetail> closeEnrollment(String enrollmentId, Map<String, dynamic> body) =>
      _mutate('POST', 'api/v1/admin/enrollments/$enrollmentId/close', body, EnrollmentDetail.fromJson);

  Future<List<StudentGuardianLink>> fetchStudentGuardians(String studentId) =>
      _list('api/v1/admin/students/$studentId/guardians', StudentGuardianLink.fromJson);

  Future<StudentGuardianLink> attachStudentGuardian(String studentId, Map<String, dynamic> body) =>
      _mutate('POST', 'api/v1/admin/students/$studentId/guardians', body, StudentGuardianLink.fromJson);

  Future<StudentGuardianLink> updateStudentGuardian(String linkId, Map<String, dynamic> body) =>
      _mutate('PATCH', 'api/v1/admin/student-guardians/$linkId', body, StudentGuardianLink.fromJson);

  String _path(String base, Map<String, String> query) {
    if (query.isEmpty) return base;
    final params = query.entries.map((e) => '${Uri.encodeQueryComponent(e.key)}=${Uri.encodeQueryComponent(e.value)}');
    return '$base?${params.join('&')}';
  }

  Future<T> _getObject<T>(String path, T Function(Map<String, dynamic>) map) async {
    final response = await _http.getJsonPath(path);
    if (response.statusCode == 401) throw AdminPeopleUnauthorized();
    if (response.statusCode != 200) throw AdminPeopleApiFailure('Request failed (${response.statusCode})');
    final decoded = jsonDecode(response.body);
    if (decoded is! Map<String, dynamic>) throw AdminPeopleApiFailure('Malformed response');
    return map(decoded);
  }

  Future<T> _mutate<T>(
    String method,
    String path,
    Map<String, dynamic> body,
    T Function(Map<String, dynamic>) map,
  ) async {
    final encoded = jsonEncode(body);
    final response = method == 'POST'
        ? await _http.postJsonPath(path, body: encoded)
        : await _http.patchJsonPath(path, body: encoded);
    if (response.statusCode == 401) throw AdminPeopleUnauthorized();
    if (response.statusCode != 200) {
      throw AdminPeopleApiFailure(_errorMessage(response));
    }
    final decoded = jsonDecode(response.body);
    if (decoded is! Map<String, dynamic>) throw AdminPeopleApiFailure('Malformed response');
    return map(decoded);
  }

  String _errorMessage(AuthenticatedHttpResponse response) {
    try {
      final decoded = jsonDecode(response.body);
      if (decoded is Map && decoded['detail'] != null) return decoded['detail'].toString();
    } catch (_) {}
    return 'Request failed (${response.statusCode})';
  }

  Future<List<T>> _list<T>(String path, T Function(Map<String, dynamic>) map) async {
    final response = await _http.getJsonPath(path);
    if (response.statusCode == 401) throw AdminPeopleUnauthorized();
    if (response.statusCode != 200) {
      throw AdminPeopleApiFailure('Request failed (${response.statusCode})');
    }
    final decoded = jsonDecode(response.body);
    if (decoded is! Map<String, dynamic> || decoded['items'] is! List) {
      throw AdminPeopleApiFailure('Malformed list response');
    }
    return (decoded['items'] as List).whereType<Map<String, dynamic>>().map(map).toList(growable: false);
  }
}
