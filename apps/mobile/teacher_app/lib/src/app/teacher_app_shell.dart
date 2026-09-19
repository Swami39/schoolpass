import 'package:flutter/material.dart';

import '../ui/home_screen.dart';
import '../ui/login_screen.dart';
import 'teacher_app_controller.dart';
import 'teacher_dependencies.dart';

class TeacherAppShell extends StatefulWidget {
  const TeacherAppShell({required this.deps, super.key});

  final TeacherDependencies deps;

  @override
  State<TeacherAppShell> createState() => _TeacherAppShellState();
}

class _TeacherAppShellState extends State<TeacherAppShell> {
  late final TeacherAppController _controller;

  @override
  void initState() {
    super.initState();
    _controller = TeacherAppController(widget.deps);
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
      title: 'SchoolPass Teacher',
      theme: ThemeData(useMaterial3: true, colorSchemeSeed: Colors.teal),
      home: AnimatedBuilder(
        animation: _controller,
        builder: (context, _) {
          switch (_controller.phase) {
            case TeacherAppPhase.booting:
              return const Scaffold(body: Center(child: CircularProgressIndicator()));
            case TeacherAppPhase.signedOut:
              return LoginScreen(controller: _controller);
            case TeacherAppPhase.signedIn:
              return HomeScreen(controller: _controller);
          }
        },
      ),
    );
  }
}
