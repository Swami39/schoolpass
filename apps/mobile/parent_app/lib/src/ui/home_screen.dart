import 'package:flutter/material.dart';

import '../app/parent_app_controller.dart';
import '../children/child_models.dart';
import 'attendance_screen.dart';
import 'bus_screen.dart';
import 'format.dart';
import 'notification_preferences_screen.dart';
import 'notifications_screen.dart';
import 'widgets.dart';

class HomeScreen extends StatelessWidget {
  const HomeScreen({required this.controller, super.key});

  final ParentAppController controller;

  @override
  Widget build(BuildContext context) {
    return AnimatedBuilder(
      animation: controller,
      builder: (context, _) {
        final theme = Theme.of(context);
        final child = controller.selectedChild;
        return Scaffold(
          appBar: AppBar(
            title: const Text('SchoolPass'),
            actions: [
              IconButton(
                onPressed: controller.logout,
                tooltip: 'Sign out',
                icon: const Icon(Icons.logout_outlined),
              ),
            ],
          ),
          body: RefreshIndicator(
            onRefresh: controller.refreshChildren,
            child: ListView(
              padding: const EdgeInsets.all(16),
              children: [
                Text(
                  '${dayGreeting()},',
                  style: theme.textTheme.titleLarge?.copyWith(fontWeight: FontWeight.w700),
                ),
                const SizedBox(height: 4),
                Text(
                  child != null ? child.displayName : 'Welcome back',
                  style: theme.textTheme.bodyLarge?.copyWith(
                    color: theme.colorScheme.onSurfaceVariant,
                  ),
                ),
                const SizedBox(height: 16),
                if (controller.loadingChildren)
                  const Center(
                    child: Padding(
                      padding: EdgeInsets.all(32),
                      child: CircularProgressIndicator(),
                    ),
                  )
                else if (controller.children.isEmpty)
                  const EmptyState(
                    icon: Icons.family_restroom_outlined,
                    title: 'No linked children',
                    subtitle: 'Ask your school to link your children to this account.',
                  )
                else ...[
                  Text('Your children', style: theme.textTheme.titleSmall),
                  const SizedBox(height: 8),
                  _ChildPicker(
                    children: controller.children,
                    selected: child,
                    onSelected: controller.selectChild,
                  ),
                ],
                if (controller.errorMessage != null) ...[
                  const SizedBox(height: 12),
                  ErrorBanner(message: controller.errorMessage!),
                ],
                const SizedBox(height: 16),
                if (child != null) ...[
                  _DashboardCard(
                    icon: Icons.fact_check_outlined,
                    title: 'Attendance',
                    subtitle: 'Daily record for the last 30 days',
                    onTap: () => Navigator.of(context).push(
                      MaterialPageRoute<void>(
                        builder: (_) => AttendanceScreen(controller: controller, studentId: child.id),
                      ),
                    ),
                  ),
                  const SizedBox(height: 12),
                  _DashboardCard(
                    icon: Icons.directions_bus_outlined,
                    title: 'Bus location',
                    subtitle: 'Live GPS tracking of the school bus',
                    onTap: () => Navigator.of(context).push(
                      MaterialPageRoute<void>(
                        builder: (_) => BusScreen(controller: controller, studentId: child.id),
                      ),
                    ),
                  ),
                  const SizedBox(height: 12),
                ],
                _DashboardCard(
                  icon: Icons.notifications_outlined,
                  title: 'Notifications',
                  subtitle: 'Alerts from the school',
                  onTap: () => Navigator.of(context).push(
                    MaterialPageRoute<void>(
                      builder: (_) => NotificationsScreen(controller: controller),
                    ),
                  ),
                ),
                const SizedBox(height: 12),
                _DashboardCard(
                  icon: Icons.tune_outlined,
                  title: 'Notification settings',
                  subtitle: 'Choose which alerts you receive',
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

/// Horizontal avatar picker — friendlier than a dropdown for 1-4 children.
class _ChildPicker extends StatelessWidget {
  const _ChildPicker({
    required this.children,
    required this.selected,
    required this.onSelected,
  });

  final List<ParentChild> children;
  final ParentChild? selected;
  final ValueChanged<ParentChild> onSelected;

  String _initials(ParentChild child) {
    final first = child.firstName.isNotEmpty ? child.firstName[0] : '';
    final last = child.lastName.isNotEmpty ? child.lastName[0] : '';
    return (first + last).toUpperCase();
  }

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    return SizedBox(
      height: 96,
      child: ListView.separated(
        scrollDirection: Axis.horizontal,
        itemCount: children.length,
        separatorBuilder: (_, __) => const SizedBox(width: 12),
        itemBuilder: (context, index) {
          final child = children[index];
          final isSelected = selected?.id == child.id;
          return GestureDetector(
            onTap: () => onSelected(child),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                Container(
                  padding: const EdgeInsets.all(3),
                  decoration: BoxDecoration(
                    shape: BoxShape.circle,
                    border: Border.all(
                      color: isSelected ? scheme.primary : scheme.outlineVariant,
                      width: isSelected ? 3 : 1.5,
                    ),
                  ),
                  child: CircleAvatar(
                    radius: 26,
                    backgroundColor:
                        isSelected ? scheme.primaryContainer : scheme.surfaceContainerHighest,
                    child: Text(
                      _initials(child),
                      style: TextStyle(
                        fontWeight: FontWeight.w700,
                        color: isSelected ? scheme.onPrimaryContainer : scheme.onSurfaceVariant,
                      ),
                    ),
                  ),
                ),
                const SizedBox(height: 4),
                SizedBox(
                  width: 72,
                  child: Text(
                    child.firstName,
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                    textAlign: TextAlign.center,
                    style: TextStyle(
                      fontSize: 12,
                      fontWeight:
                          isSelected ? FontWeight.w700 : FontWeight.w400,
                    ),
                  ),
                ),
              ],
            ),
          );
        },
      ),
    );
  }
}

class _DashboardCard extends StatelessWidget {
  const _DashboardCard({
    required this.icon,
    required this.title,
    required this.subtitle,
    required this.onTap,
  });

  final IconData icon;
  final String title;
  final String subtitle;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final scheme = theme.colorScheme;
    return Card(
      child: ListTile(
        contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
        leading: Container(
          width: 48,
          height: 48,
          decoration: BoxDecoration(
            color: scheme.primaryContainer,
            borderRadius: BorderRadius.circular(14),
          ),
          child: Icon(icon, color: scheme.onPrimaryContainer),
        ),
        title: Text(title, style: const TextStyle(fontWeight: FontWeight.w600)),
        subtitle: Text(subtitle),
        trailing: Icon(Icons.chevron_right, color: scheme.onSurfaceVariant),
        onTap: onTap,
      ),
    );
  }
}
