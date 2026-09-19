import 'package:flutter/material.dart';

import 'src/app/teacher_app_shell.dart';
import 'src/app/teacher_dependencies.dart';

void main() {
  runApp(TeacherAppShell(deps: TeacherDependencies.production()));
}
