import 'dart:convert';

import '../http/authenticated_http_client.dart';
import 'school_profile_models.dart';

class AdminSchoolUnauthorized implements Exception {}

class AdminSchoolApiFailure implements Exception {
  AdminSchoolApiFailure(this.message);
  final String message;
}

class AdminSchoolApi {
  AdminSchoolApi(this._http);

  final AuthenticatedHttpClient _http;

  Future<SchoolProfile> fetchProfile() async {
    final response = await _http.getJsonPath('api/v1/admin/school');
    if (response.statusCode == 401) {
      throw AdminSchoolUnauthorized();
    }
    if (response.statusCode != 200) {
      throw AdminSchoolApiFailure('Could not load school profile (${response.statusCode})');
    }
    final decoded = jsonDecode(response.body);
    if (decoded is! Map<String, dynamic>) {
      throw AdminSchoolApiFailure('Malformed school profile response');
    }
    return SchoolProfile.fromJson(decoded);
  }

  Future<SchoolProfile> updateProfile(Map<String, dynamic> body) async {
    final response = await _http.patchJsonPath(
      'api/v1/admin/school',
      body: jsonEncode(body),
    );
    if (response.statusCode == 401) {
      throw AdminSchoolUnauthorized();
    }
    if (response.statusCode == 403) {
      throw AdminSchoolApiFailure('You do not have permission to update the school profile');
    }
    if (response.statusCode == 422) {
      throw AdminSchoolApiFailure('Some profile fields are invalid');
    }
    if (response.statusCode != 200) {
      throw AdminSchoolApiFailure('Could not save school profile (${response.statusCode})');
    }
    final decoded = jsonDecode(response.body);
    if (decoded is! Map<String, dynamic>) {
      throw AdminSchoolApiFailure('Malformed school profile response');
    }
    return SchoolProfile.fromJson(decoded);
  }
}
