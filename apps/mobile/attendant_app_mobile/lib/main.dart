import 'package:attendant_app/attendant_app.dart';
import 'package:attendant_secure_storage/attendant_secure_storage.dart';
import 'package:flutter/material.dart';

void main() {
  final deps = AttendantDependencies.create(
    apiOrigin: Uri.parse(
      const String.fromEnvironment('SCHOOLPASS_API_ORIGIN', defaultValue: 'http://127.0.0.1:8000'),
    ),
    tokenStore: createProductionTokenStore(),
  );
  runApp(AttendantAppShell(deps: deps));
}
