import 'package:flutter/material.dart';
import 'package:schoolpass_design/schoolpass_design.dart';

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
    return Scaffold(
      body: Center(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            const BrandMark(icon: Icons.directions_bus),
            const SizedBox(height: 20),
            Text(
              'SchoolPass',
              style: DesignTypography.heroTitle(
                color: DesignColors.ink,
                size: 28,
              ),
            ),
            const SizedBox(height: 4),
            const Text(
              'Bus Attendant',
              style: TextStyle(
                fontSize: 15,
                fontWeight: FontWeight.w600,
                color: DesignColors.ink2,
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
