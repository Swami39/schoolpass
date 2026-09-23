import 'package:flutter/material.dart';

import '../ui/app_theme.dart';
import '../ui/home_screen.dart';
import '../ui/login_screen.dart';
import '../ui/widgets.dart';
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
      theme: buildParentTheme(),
      home: AnimatedBuilder(
        animation: _controller,
        builder: (context, _) {
          switch (_controller.phase) {
            case ParentAppPhase.booting:
              return const _BootSplash();
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
            const BrandMark(icon: Icons.school),
            const SizedBox(height: 20),
            Text('SchoolPass', style: theme.textTheme.headlineMedium?.copyWith(fontWeight: FontWeight.w800)),
            const SizedBox(height: 4),
            Text('Parent', style: theme.textTheme.titleMedium?.copyWith(color: theme.colorScheme.onSurfaceVariant)),
            const SizedBox(height: 32),
            const CircularProgressIndicator(),
          ],
        ),
      ),
    );
  }
}
