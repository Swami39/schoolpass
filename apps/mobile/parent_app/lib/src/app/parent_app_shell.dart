import 'package:flutter/material.dart';

import '../ui/home_screen.dart';
import '../ui/login_screen.dart';
import 'parent_app_controller.dart';
import 'parent_dependencies.dart';

class ParentAppShell extends StatefulWidget {
  const ParentAppShell({required this.deps, super.key});

  final ParentDependencies deps;

  @override
  State<ParentAppShell> createState() => _ParentAppShellState();
}

class _ParentAppShellState extends State<ParentAppShell> {
  late final ParentAppController _controller;

  @override
  void initState() {
    super.initState();
    _controller = ParentAppController(widget.deps);
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
      title: 'SchoolPass Parent',
      theme: ThemeData(useMaterial3: true, colorSchemeSeed: Colors.indigo),
      home: AnimatedBuilder(
        animation: _controller,
        builder: (context, _) {
          switch (_controller.phase) {
            case ParentAppPhase.booting:
              return const Scaffold(body: Center(child: CircularProgressIndicator()));
            case ParentAppPhase.signedOut:
              return LoginScreen(controller: _controller);
            case ParentAppPhase.signedIn:
              return HomeScreen(controller: _controller);
          }
        },
      ),
    );
  }
}
