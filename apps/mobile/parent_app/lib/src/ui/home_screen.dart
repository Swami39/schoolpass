import 'package:flutter/material.dart';

import '../app/parent_app_controller.dart';
import '../children/child_models.dart';
import 'attendance_screen.dart';
import 'bus_screen.dart';
import 'notification_preferences_screen.dart';
import 'notifications_screen.dart';

class HomeScreen extends StatelessWidget {
  const HomeScreen({required this.controller, super.key});

  final ParentAppController controller;

  @override
  Widget build(BuildContext context) {
    return AnimatedBuilder(
      animation: controller,
      builder: (context, _) {
        final child = controller.selectedChild;
        return Scaffold(
          appBar: AppBar(
            title: const Text('Home'),
            actions: [
              IconButton(
                onPressed: controller.logout,
                tooltip: 'Sign out',
                icon: const Icon(Icons.logout),
              ),
            ],
          ),
          body: RefreshIndicator(
            onRefresh: controller.refreshChildren,
            child: ListView(
              padding: const EdgeInsets.all(16),
              children: [
                Text('Your children', style: Theme.of(context).textTheme.titleMedium),
                const SizedBox(height: 8),
                if (controller.loadingChildren)
                  const Center(child: Padding(padding: EdgeInsets.all(24), child: CircularProgressIndicator()))
                else if (controller.children.isEmpty)
                  const Text('No linked children for this account.')
                else
                  _ChildSelector(
                    children: controller.children,
                    selected: child,
                    onSelected: controller.selectChild,
                  ),
                if (controller.errorMessage != null) ...[
                  const SizedBox(height: 8),
                  Text(controller.errorMessage!, style: TextStyle(color: Theme.of(context).colorScheme.error)),
                ],
                const SizedBox(height: 24),
                if (child != null) ...[
                  _NavTile(
                    icon: Icons.fact_check_outlined,
                    label: 'Attendance',
                    onTap: () => Navigator.of(context).push(
                      MaterialPageRoute<void>(
                        builder: (_) => AttendanceScreen(controller: controller, studentId: child.id),
                      ),
                    ),
                  ),
                  _NavTile(
                    icon: Icons.directions_bus_outlined,
                    label: 'Bus location',
                    onTap: () => Navigator.of(context).push(
                      MaterialPageRoute<void>(
                        builder: (_) => BusScreen(controller: controller, studentId: child.id),
                      ),
                    ),
                  ),
                ],
                _NavTile(
                  icon: Icons.notifications_outlined,
                  label: 'Notifications',
                  onTap: () => Navigator.of(context).push(
                    MaterialPageRoute<void>(
                      builder: (_) => NotificationsScreen(controller: controller),
                    ),
                  ),
                ),
                _NavTile(
                  icon: Icons.settings_outlined,
                  label: 'Notification settings',
                  onTap: () => Navigator.of(context).push(
                    MaterialPageRoute<void>(
                      builder: (_) => NotificationPreferencesScreen(controller: controller),
                    ),
                  ),
                ),
              ],
            ),
          ),
        );
      },
    );
  }
}

class _ChildSelector extends StatelessWidget {
  const _ChildSelector({
    required this.children,
    required this.selected,
    required this.onSelected,
  });

  final List<ParentChild> children;
  final ParentChild? selected;
  final ValueChanged<ParentChild> onSelected;

  @override
  Widget build(BuildContext context) {
    return DropdownMenu<ParentChild>(
      label: const Text('Selected child'),
      initialSelection: selected,
      dropdownMenuEntries: children
          .map(
            (c) => DropdownMenuEntry(
              value: c,
              label: c.displayName,
            ),
          )
          .toList(),
      onSelected: (value) {
        if (value != null) {
          onSelected(value);
        }
      },
    );
  }
}

class _NavTile extends StatelessWidget {
  const _NavTile({required this.icon, required this.label, required this.onTap});

  final IconData icon;
  final String label;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return Card(
      child: ListTile(
        leading: Icon(icon),
        title: Text(label),
        trailing: const Icon(Icons.chevron_right),
        onTap: onTap,
      ),
    );
  }
}
