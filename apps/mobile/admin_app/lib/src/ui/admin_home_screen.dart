import 'package:flutter/material.dart';

import '../app/admin_app_controller.dart';
import '../app/admin_dependencies.dart';
import 'academic_hub_screen.dart';
import 'operations_hub_screen.dart';
import 'people_hub_screen.dart';
import 'school_profile_screen.dart';

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
          body: _bodyForSection(),
        );
      },
    );
  }

  Widget _bodyForSection() {
    switch (controller.section) {
      case AdminSection.school:
        return SchoolProfileScreen(controller: controller);
      case AdminSection.dashboard:
        return const _PlaceholderPanel(
          title: 'Dashboard',
          message: 'Operational dashboards will be available in a later phase.',
        );
      case AdminSection.academic:
        return AcademicHubScreen(deps: deps);
      case AdminSection.teachers:
      case AdminSection.students:
      case AdminSection.guardians:
        return PeopleHubScreen(deps: deps);
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
