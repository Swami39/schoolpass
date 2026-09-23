import 'package:flutter/material.dart';

import '../ui/app_theme.dart';
import '../ui/home_screen.dart';
import '../ui/login_screen.dart';
import '../ui/widgets.dart';
import 'attendant_app_controller.dart';
import 'attendant_dependencies.dart';

class AttendantAppShell extends StatefulWidget {
  const AttendantAppShell({required this.deps, super.key});

  final AttendantDependencies deps;

  @override
  State<AttendantAppShell> createState() => _AttendantAppShellState();
}

class _AttendantAppShellState extends State<AttendantAppShell> {
  late final AttendantAppController _controller;

  @override
  void initState() {
    super.initState();
    _controller = AttendantAppController(widget.deps);
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
      title: 'SchoolPass Bus Attendant',
      theme: buildAttendantTheme(),
      home: AnimatedBuilder(
        animation: _controller,
        builder: (context, _) {
          switch (_controller.phase) {
            case AttendantAppPhase.booting:
              return const _BootSplash();
            case AttendantAppPhase.signedOut:
              return LoginScreen(controller: _controller);
            case AttendantAppPhase.signedIn:
              return HomeScreen(controller: _controller);
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
            const BrandMark(icon: Icons.directions_bus),
            const SizedBox(height: 20),
            Text('SchoolPass', style: theme.textTheme.headlineMedium?.copyWith(fontWeight: FontWeight.w800)),
            const SizedBox(height: 4),
            Text('Bus Attendant', style: theme.textTheme.titleMedium?.copyWith(color: theme.colorScheme.onSurfaceVariant)),
            const SizedBox(height: 32),
            const CircularProgressIndicator(),
          ],
        ),
      ),
    );
  }
}
