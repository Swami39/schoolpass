import 'package:flutter/material.dart';

import '../app/admin_app_controller.dart';
import '../app/admin_dependencies.dart';
import 'academic_hub_screen.dart';
import 'admin_widgets.dart';
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

  static const _sectionIcons = <AdminSection, IconData>{
    AdminSection.dashboard: Icons.dashboard_outlined,
    AdminSection.school: Icons.home_work_outlined,
    AdminSection.academic: Icons.menu_book_outlined,
    AdminSection.teachers: Icons.badge_outlined,
    AdminSection.students: Icons.school_outlined,
    AdminSection.guardians: Icons.family_restroom_outlined,
    AdminSection.cards: Icons.credit_card_outlined,
    AdminSection.transport: Icons.directions_bus_outlined,
    AdminSection.rfid: Icons.sensors_outlined,
    AdminSection.operations: Icons.settings_outlined,
    AdminSection.audit: Icons.history_outlined,
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
                padding: EdgeInsets.zero,
                children: [
                  _DrawerBrand(),
                  const SizedBox(height: 8),
                  for (final entry in _sections.entries)
                    Padding(
                      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 1),
                      child: ListTile(
                        leading: Icon(_sectionIcons[entry.key]),
                        selected: controller.section == entry.key,
                        title: Text(entry.value),
                        onTap: () {
                          Navigator.of(context).pop();
                          controller.selectSection(entry.key);
                        },
                      ),
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

class _DrawerBrand extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    return Container(
      padding: const EdgeInsets.fromLTRB(20, 28, 20, 20),
      decoration: BoxDecoration(
        gradient: LinearGradient(
          colors: [scheme.primary, scheme.tertiary],
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
        ),
      ),
      child: Row(
        children: [
          const BrandMark(icon: Icons.admin_panel_settings, size: 52),
          const SizedBox(width: 14),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  'SchoolPass',
                  style: TextStyle(
                    color: scheme.onPrimary,
                    fontSize: 20,
                    fontWeight: FontWeight.w800,
                  ),
                ),
                Text(
                  'Admin console',
                  style: TextStyle(
                    color: scheme.onPrimary.withValues(alpha: 0.85),
                    fontSize: 13,
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

class _DashboardPanel extends StatelessWidget {
  const _DashboardPanel({required this.controller, required this.deps});

  final AdminAppController controller;
  final AdminDependencies deps;

  void _openPeople(BuildContext context) {
    Navigator.of(context).push(
      MaterialPageRoute(
        builder: (_) => Scaffold(
          appBar: AppBar(title: const Text('People')),
          body: PeopleHubScreen(deps: deps),
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        Text('Get the school ready', style: theme.textTheme.headlineSmall),
        const SizedBox(height: 4),
        Text(
          'Add students with their parents, or import the whole school from one CSV.',
          style: theme.textTheme.bodyMedium?.copyWith(
            color: theme.colorScheme.onSurfaceVariant,
          ),
        ),
        const SizedBox(height: 16),
        const SectionHeader(title: 'Quick actions'),
        const SizedBox(height: 8),
        AdminSectionCard(
          icon: Icons.person_add_alt_outlined,
          title: 'Add a student',
          subtitle: 'Create the child, class enrollment, and parent login together',
          onTap: () => Navigator.of(context).push(
            MaterialPageRoute(builder: (_) => StudentFormScreen(deps: deps)),
          ),
        ),
        const SizedBox(height: 12),
        AdminSectionCard(
          icon: Icons.upload_file_outlined,
          title: 'Bulk import school data',
          subtitle: 'One CSV for classes, teachers, students, and parent links',
          onTap: () => Navigator.of(context).push(
            MaterialPageRoute(builder: (_) => ImportsHubScreen(deps: deps)),
          ),
        ),
        const SizedBox(height: 20),
        const SectionHeader(title: 'All sections'),
        const SizedBox(height: 8),
        AdminSectionCard(
          icon: Icons.groups_outlined,
          title: 'People',
          subtitle: 'Students, guardians, and staff',
          onTap: () => _openPeople(context),
        ),
        const SizedBox(height: 12),
        AdminSectionCard(
          icon: Icons.menu_book_outlined,
          title: 'Academic',
          subtitle: 'Years, classes, sections, and subjects',
          onTap: () => controller.selectSection(AdminSection.academic),
        ),
        const SizedBox(height: 12),
        AdminSectionCard(
          icon: Icons.settings_outlined,
          title: 'Operations',
          subtitle: 'Buses, trips, cards, RFID readers, and boarding',
          onTap: () => controller.selectSection(AdminSection.operations),
        ),
        const SizedBox(height: 12),
        AdminSectionCard(
          icon: Icons.upload_outlined,
          title: 'Imports',
          subtitle: 'Validate and apply CSV onboarding data',
          onTap: () => Navigator.of(context).push(
            MaterialPageRoute(builder: (_) => ImportsHubScreen(deps: deps)),
          ),
        ),
        const SizedBox(height: 12),
        AdminSectionCard(
          icon: Icons.home_work_outlined,
          title: 'School profile',
          subtitle: 'Name, timezone, and contact details',
          onTap: () => controller.selectSection(AdminSection.school),
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
        child: EmptyState(
          icon: Icons.construction_outlined,
          title: title,
          subtitle: message,
        ),
      ),
    );
  }
}
