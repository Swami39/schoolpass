import 'package:flutter/material.dart';

import '../app/admin_app_controller.dart';
import '../app/admin_dependencies.dart';
import 'academic_hub_screen.dart';
import 'imports_hub_screen.dart';
import 'operations_hub_screen.dart';
import 'people_hub_screen.dart';
import 'school_profile_screen.dart';
import 'student_form_screen.dart';

class AdminHomeScreen extends StatelessWidget {
  const AdminHomeScreen({required this.controller, required this.deps, super.key});

  final AdminAppController controller;
  final AdminDependencies deps;

  static const _sections = <AdminSection, String>{
    AdminSection.dashboard: 'Dashboard',
    AdminSection.school: 'School',
    AdminSection.academic: 'Academic',
    AdminSection.teachers: 'Teachers',
    AdminSection.students: 'Students',
    AdminSection.guardians: 'Guardians',
    AdminSection.cards: 'Cards',
    AdminSection.transport: 'Transport',
    AdminSection.rfid: 'RFID',
    AdminSection.operations: 'Operations',
    AdminSection.audit: 'Audit',
  };

  @override
  Widget build(BuildContext context) {
    return AnimatedBuilder(
      animation: controller,
      builder: (context, _) {
        return Scaffold(
          appBar: AppBar(
            title: Text(_sections[controller.section] ?? 'Admin'),
            actions: [
              IconButton(
                onPressed: controller.logout,
                icon: const Icon(Icons.logout),
                tooltip: 'Sign out',
              ),
            ],
          ),
          drawer: Drawer(
            child: SafeArea(
              child: ListView(
              children: [
                const DrawerHeader(
                  child: Text('SchoolPass Admin', style: TextStyle(fontSize: 20)),
                ),
                for (final entry in _sections.entries)
                  ListTile(
                    selected: controller.section == entry.key,
                    title: Text(entry.value),
                    onTap: () {
                      Navigator.of(context).pop();
                      controller.selectSection(entry.key);
                    },
                  ),
              ],
            ),
            ),
          ),
          body: _bodyForSection(context),
        );
      },
    );
  }

  Widget _bodyForSection(BuildContext context) {
    switch (controller.section) {
      case AdminSection.school:
        return SchoolProfileScreen(controller: controller);
      case AdminSection.dashboard:
        return _DashboardPanel(controller: controller, deps: deps);
      case AdminSection.academic:
        return AcademicHubScreen(deps: deps);
      case AdminSection.teachers:
        return PeopleHubScreen.staffList(context, deps, useScaffold: false);
      case AdminSection.students:
        return PeopleHubScreen.studentsList(context, deps, useScaffold: false);
      case AdminSection.guardians:
        return PeopleHubScreen.guardiansList(context, deps, useScaffold: false);
      case AdminSection.cards:
      case AdminSection.transport:
      case AdminSection.rfid:
      case AdminSection.operations:
        return OperationsHubScreen(deps: deps);
      default:
        return _PlaceholderPanel(
          title: _sections[controller.section] ?? 'Section',
          message: 'This section is not available yet.',
        );
    }
  }
}

class _DashboardPanel extends StatelessWidget {
  const _DashboardPanel({required this.controller, required this.deps});

  final AdminAppController controller;
  final AdminDependencies deps;

  @override
  Widget build(BuildContext context) {
    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        Text('Get the school ready', style: Theme.of(context).textTheme.titleLarge),
        const SizedBox(height: 8),
        const Text('Add students with their parents, or import the whole school from one CSV.'),
        const SizedBox(height: 16),
        Card(
          child: ListTile(
            leading: const Icon(Icons.person_add_alt),
            title: const Text('Add a student'),
            subtitle: const Text('Create the child, class enrollment, and parent login together'),
            onTap: () => Navigator.of(context).push(
              MaterialPageRoute(builder: (_) => StudentFormScreen(deps: deps)),
            ),
          ),
        ),
        Card(
          child: ListTile(
            leading: const Icon(Icons.upload_file),
            title: const Text('Bulk upload school data'),
            subtitle: const Text('One CSV for classes, teachers, students, and parent links'),
            onTap: () => Navigator.of(context).push(
              MaterialPageRoute(builder: (_) => ImportsHubScreen(deps: deps)),
            ),
          ),
        ),
        Card(
          child: ListTile(
            leading: const Icon(Icons.school),
            title: const Text('Students'),
            onTap: () => controller.selectSection(AdminSection.students),
          ),
        ),
        Card(
          child: ListTile(
            leading: const Icon(Icons.family_restroom),
            title: const Text('Parents / guardians'),
            onTap: () => controller.selectSection(AdminSection.guardians),
          ),
        ),
      ],
    );
  }
}

class _PlaceholderPanel extends StatelessWidget {
  const _PlaceholderPanel({required this.title, required this.message});

  final String title;
  final String message;

  @override
  Widget build(BuildContext context) {
    return Center(
      child: ConstrainedBox(
        constraints: const BoxConstraints(maxWidth: 420),
        child: Padding(
          padding: const EdgeInsets.all(24),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Text(title, style: Theme.of(context).textTheme.headlineSmall),
              const SizedBox(height: 12),
              Text(message, textAlign: TextAlign.center),
            ],
          ),
        ),
      ),
    );
  }
}
