import 'package:flutter/material.dart';
import 'package:schoolpass_design/schoolpass_design.dart';

import '../app/admin_app_controller.dart';
import '../app/admin_dependencies.dart';
import 'admin_widgets.dart';
import 'imports_hub_screen.dart';
import 'operations_hub_screen.dart';
import 'people_hub_screen.dart';
import 'school_structure_screen.dart';
import 'setup_checklist_screen.dart';

/// The redesigned admin home: six workflow areas instead of eleven
/// feature silos. Setup (the guided checklist) is the default screen.
class AdminHomeScreen extends StatelessWidget {
  const AdminHomeScreen({required this.controller, required this.deps, super.key});

  final AdminAppController controller;
  final AdminDependencies deps;

  static const _sections = <AdminSection, String>{
    AdminSection.setup: 'Setup',
    AdminSection.structure: 'Classes & sections',
    AdminSection.directory: 'Directory',
    AdminSection.operations: 'Operations',
    AdminSection.imports: 'Imports',
    AdminSection.audit: 'Audit',
  };

  static const _sectionIcons = <AdminSection, IconData>{
    AdminSection.setup: Icons.checklist_outlined,
    AdminSection.structure: Icons.account_tree_outlined,
    AdminSection.directory: Icons.groups_outlined,
    AdminSection.operations: Icons.settings_outlined,
    AdminSection.imports: Icons.upload_file_outlined,
    AdminSection.audit: Icons.history_outlined,
  };

  static const _sectionDescriptions = <AdminSection, String>{
    AdminSection.setup: 'Guided steps to get the school running',
    AdminSection.structure: 'Years, classes, sections, and their people',
    AdminSection.directory: 'Everyone: staff, students, and parents',
    AdminSection.operations: 'Buses, trips, cards, RFID readers, and events',
    AdminSection.imports: 'Validate and apply CSV onboarding data',
    AdminSection.audit: 'What changed and when',
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
                  const _DrawerBrand(),
                  const SizedBox(height: 8),
                  for (final entry in _sections.entries)
                    Padding(
                      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 4),
                      child: Panel(
                        padding: const EdgeInsets.all(14),
                        color: controller.section == entry.key
                            ? DesignColors.brandSoft
                            : null,
                        borderColor: controller.section == entry.key
                            ? DesignColors.brand
                            : null,
                        onTap: () {
                          Navigator.of(context).pop();
                          controller.selectSection(entry.key);
                        },
                        child: Row(
                          children: [
                            Container(
                              width: 44,
                              height: 44,
                              decoration: BoxDecoration(
                                color: controller.section == entry.key
                                    ? Colors.white
                                    : DesignColors.brandSoft,
                                borderRadius: BorderRadius.circular(14),
                              ),
                              child: Icon(
                                _sectionIcons[entry.key],
                                color: DesignColors.brandInk,
                              ),
                            ),
                            const SizedBox(width: 12),
                            Expanded(
                              child: Column(
                                crossAxisAlignment: CrossAxisAlignment.start,
                                children: [
                                  Text(
                                    entry.value,
                                    style: const TextStyle(
                                      fontWeight: FontWeight.w700,
                                      fontSize: 15,
                                      color: DesignColors.ink,
                                    ),
                                  ),
                                  const SizedBox(height: 2),
                                  Text(
                                    _sectionDescriptions[entry.key] ?? '',
                                    maxLines: 1,
                                    overflow: TextOverflow.ellipsis,
                                    style: const TextStyle(
                                      fontSize: 12,
                                      color: DesignColors.ink2,
                                    ),
                                  ),
                                ],
                              ),
                            ),
                            const Icon(
                              Icons.chevron_right,
                              color: DesignColors.ink3,
                            ),
                          ],
                        ),
                      ),
                    ),
                ],
              ),
            ),
          ),
          body: _bodyForSection(),
        );
      },
    );
  }

  Widget _bodyForSection() {
    switch (controller.section) {
      case AdminSection.setup:
        return SetupChecklistScreen(controller: controller, deps: deps);
      case AdminSection.structure:
        return SchoolStructureScreen(deps: deps);
      case AdminSection.directory:
        return PeopleHubScreen(deps: deps);
      case AdminSection.operations:
        return OperationsHubScreen(deps: deps);
      case AdminSection.imports:
        return ImportsHubScreen(deps: deps);
      case AdminSection.audit:
        return const _PlaceholderPanel(
          title: 'Audit',
          message: 'A change history view is not available in the app yet.',
        );
    }
  }
}

class _DrawerBrand extends StatelessWidget {
  const _DrawerBrand();

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.fromLTRB(20, 28, 20, 20),
      decoration: const BoxDecoration(gradient: DesignColors.brandGradient),
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
                  style: DesignTypography.heroTitle(size: 20),
                ),
                Text(
                  'Admin console',
                  style: TextStyle(
                    color: Colors.white.withValues(alpha: 0.85),
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
