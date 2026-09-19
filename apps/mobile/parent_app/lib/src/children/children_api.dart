import 'dart:convert';

import '../http/authenticated_http_client.dart';
import 'child_models.dart';

class ChildrenApi {
  ChildrenApi(this._http);

  final AuthenticatedHttpClient _http;

  Future<List<ParentChild>> fetchChildren() async {
    final response = await _http.getJsonPath('/api/v1/parent/children');
    if (response.statusCode == 401 || response.statusCode == 403) {
      throw ChildrenUnauthorized();
    }
    if (response.statusCode != 200) {
      throw ChildrenRequestFailure(response.statusCode);
    }
    final decoded = jsonDecode(response.body);
    if (decoded is! Map<String, dynamic>) {
      throw ChildrenParseFailure();
    }
    final items = decoded['items'];
    if (items is! List) {
      throw ChildrenParseFailure();
    }
    return items
        .whereType<Map<String, dynamic>>()
        .map(ParentChild.fromJson)
        .toList(growable: false);
  }
}

class ChildrenUnauthorized implements Exception {}

class ChildrenRequestFailure implements Exception {
  ChildrenRequestFailure(this.statusCode);
  final int statusCode;
}

class ChildrenParseFailure implements Exception {}
