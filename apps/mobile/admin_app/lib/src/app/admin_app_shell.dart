import 'package:flutter/material.dart';

import '../ui/admin_home_screen.dart';
import '../ui/admin_theme.dart';
import '../ui/admin_widgets.dart';
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
      theme: buildAdminTheme(),
      home: AnimatedBuilder(
        animation: _controller,
        builder: (context, _) {
          switch (_controller.phase) {
            case AdminAppPhase.booting:
              return const _BootSplash();
            case AdminAppPhase.signedOut:
              return LoginScreen(controller: _controller);
            case AdminAppPhase.signedIn:
              return AdminHomeScreen(controller: _controller, deps: widget.deps);
          }
        },
      ),
    );
  }
}

class _BootSplash extends StatelessWidget {
  const _BootSplash();

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Scaffold(
      body: Center(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            const BrandMark(icon: Icons.admin_panel_settings),
            const SizedBox(height: 20),
            Text(
              'SchoolPass',
              style: theme.textTheme.headlineMedium?.copyWith(fontWeight: FontWeight.w800),
            ),
            const SizedBox(height: 4),
            Text(
              'Admin',
              style: theme.textTheme.titleMedium?.copyWith(
                color: theme.colorScheme.onSurfaceVariant,
              ),
            ),
            const SizedBox(height: 8),
            Text(
              'Run your school from one place.',
              style: theme.textTheme.bodyMedium?.copyWith(
                color: theme.colorScheme.onSurfaceVariant,
              ),
            ),
            const SizedBox(height: 32),
            const CircularProgressIndicator(),
          ],
        ),
      ),
    );
  }
}
