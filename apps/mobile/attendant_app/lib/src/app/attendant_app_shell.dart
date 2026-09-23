import 'package:flutter/material.dart';

import '../ui/home_screen.dart';
import '../ui/login_screen.dart';
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
      theme: ThemeData(useMaterial3: true, colorSchemeSeed: Colors.deepOrange),
      home: AnimatedBuilder(
        animation: _controller,
        builder: (context, _) {
          switch (_controller.phase) {
            case AttendantAppPhase.booting:
              return const Scaffold(body: Center(child: CircularProgressIndicator()));
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
