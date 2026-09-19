import 'dart:convert';

import '../http/authenticated_http_client.dart';

class AdminImportsApiFailure implements Exception {
  AdminImportsApiFailure(this.message);
  final String message;
}

class ImportValidateResult {
  const ImportValidateResult({
    required this.importType,
    required this.contentDigest,
    required this.rowCount,
    required this.validRowCount,
    required this.errors,
  });

  final String importType;
  final String contentDigest;
  final int rowCount;
  final int validRowCount;
  final List<ImportRowError> errors;

  factory ImportValidateResult.fromJson(Map<String, dynamic> json) => ImportValidateResult(
        importType: json['import_type'] as String,
        contentDigest: json['content_digest'] as String,
        rowCount: json['row_count'] as int,
        validRowCount: json['valid_row_count'] as int,
        errors: (json['errors'] as List<dynamic>? ?? const [])
            .whereType<Map<String, dynamic>>()
            .map(ImportRowError.fromJson)
            .toList(growable: false),
      );
}

class ImportRowError {
  const ImportRowError({required this.rowNumber, required this.message});

  final int rowNumber;
  final String message;

  factory ImportRowError.fromJson(Map<String, dynamic> json) => ImportRowError(
        rowNumber: json['row_number'] as int,
        message: json['message'] as String,
      );
}

class ImportApplyResult {
  const ImportApplyResult({
    required this.status,
    required this.appliedCount,
    required this.skippedCount,
    required this.rowCount,
  });

  final String status;
  final int appliedCount;
  final int skippedCount;
  final int rowCount;

  factory ImportApplyResult.fromJson(Map<String, dynamic> json) => ImportApplyResult(
        status: json['status'] as String,
        appliedCount: json['applied_count'] as int,
        skippedCount: json['skipped_count'] as int,
        rowCount: json['row_count'] as int,
      );
}

class AdminImportsApi {
  AdminImportsApi(this._http);

  final AuthenticatedHttpClient _http;

  Future<String> fetchTemplateHeader(String importType) async {
    final response = await _http.getJsonPath('api/v1/admin/imports/types/$importType/template');
    if (response.statusCode != 200) {
      throw AdminImportsApiFailure('Template request failed (${response.statusCode})');
    }
    final decoded = jsonDecode(response.body);
    if (decoded is! Map<String, dynamic>) throw AdminImportsApiFailure('Malformed template');
    return decoded['csv_header_line'] as String;
  }

  Future<ImportValidateResult> validateCsv({
    required String importType,
    required List<int> bytes,
    required String filename,
  }) async {
    final response = await _http.postMultipartPath(
      'api/v1/admin/imports/$importType/validate',
      fields: const {},
      files: {'file': MultipartFilePayload(filename: filename, bytes: bytes)},
    );
    if (response.statusCode != 200) {
      throw AdminImportsApiFailure('Validation failed (${response.statusCode}): ${response.body}');
    }
    final decoded = jsonDecode(response.body);
    if (decoded is! Map<String, dynamic>) throw AdminImportsApiFailure('Malformed validation response');
    return ImportValidateResult.fromJson(decoded);
  }

  Future<ImportApplyResult> applyCsv({
    required String importType,
    required List<int> bytes,
    required String filename,
    required String contentDigest,
  }) async {
    final response = await _http.postMultipartPath(
      'api/v1/admin/imports/$importType/apply',
      fields: {'confirm': 'true', 'content_digest': contentDigest},
      files: {'file': MultipartFilePayload(filename: filename, bytes: bytes)},
    );
    if (response.statusCode != 200) {
      throw AdminImportsApiFailure('Apply failed (${response.statusCode}): ${response.body}');
    }
    final decoded = jsonDecode(response.body);
    if (decoded is! Map<String, dynamic>) throw AdminImportsApiFailure('Malformed apply response');
    return ImportApplyResult.fromJson(decoded);
  }
}
