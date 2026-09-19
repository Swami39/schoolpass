import 'package:flutter/material.dart';
import 'package:parent_app/parent_app.dart';
import 'package:parent_secure_storage/parent_secure_storage.dart';

void main() {
  final deps = ParentDependencies.create(
    apiOrigin: Uri.parse(
      const String.fromEnvironment('SCHOOLPASS_API_ORIGIN', defaultValue: 'http://127.0.0.1:8000'),
    ),
    tokenStore: createProductionTokenStore(),
    pushProvider: FakePlatformPushProvider(),
  );
  runApp(ParentAppShell(deps: deps));
}
