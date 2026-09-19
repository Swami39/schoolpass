import 'package:flutter/material.dart';

import '../ui/admin_home_screen.dart';
import '../ui/login_screen.dart';
import 'admin_app_controller.dart';
import 'admin_dependencies.dart';

class AdminAppShell extends StatefulWidget {
  const AdminAppShell({required this.deps, super.key});

  final AdminDependencies deps;

  @override
  State<AdminAppShell> createState() => _AdminAppShellState();
}

class _AdminAppShellState extends State<AdminAppShell> {
  late final AdminAppController _controller;

  @override
  void initState() {
    super.initState();
    _controller = AdminAppController(widget.deps);
    _controller.bootstrap();
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'SchoolPass Admin',
      theme: ThemeData(useMaterial3: true, colorSchemeSeed: Colors.indigo),
      home: AnimatedBuilder(
        animation: _controller,
        builder: (context, _) {
          switch (_controller.phase) {
            case AdminAppPhase.booting:
              return const Scaffold(body: Center(child: CircularProgressIndicator()));
            case AdminAppPhase.signedOut:
              return LoginScreen(controller: _controller);
            case AdminAppPhase.signedIn:
              return AdminHomeScreen(controller: _controller);
          }
        },
      ),
    );
  }
}
