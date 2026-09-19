import 'package:flutter/material.dart';
import 'package:teacher_app/teacher_app.dart';
import 'package:teacher_secure_storage/teacher_secure_storage.dart';

void main() {
  final deps = TeacherDependencies.create(
    apiOrigin: Uri.parse(
      const String.fromEnvironment('SCHOOLPASS_API_ORIGIN', defaultValue: 'http://127.0.0.1:8000'),
    ),
    tokenStore: createProductionTokenStore(),
  );
  runApp(TeacherAppShell(deps: deps));
}
