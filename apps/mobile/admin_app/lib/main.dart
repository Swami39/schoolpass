import 'package:flutter/material.dart';

import 'src/app/admin_app_shell.dart';
import 'src/app/admin_dependencies.dart';

void main() {
  runApp(AdminAppShell(deps: AdminDependencies.production()));
}
