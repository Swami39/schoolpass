import 'package:flutter/material.dart';
import 'package:schoolpass_design/schoolpass_design.dart';

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
        final child = controller.selectedChild;
        final status = context.status;
        return Scaffold(
          appBar: AppBar(
            title: const DesignAppBarTitle('SchoolPass', subtitle: 'Parent'),
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
                // NOTE: the controller only carries the linked-children list
                // (child.status is the enrollment status, e.g. "active");
                // there is no live presence feed, so the hero shows the
                // selected child's name with "No updates yet" and no live
                // pulse. Wire live: true + a real status line once the
                // backend exposes one.
                HeroCard(
                  eyebrow: dayGreeting(),
                  title: child != null ? child.displayName : 'Welcome back',
                  subtitle: 'No updates yet',
                ),
                const SizedBox(height: 20),
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
                  const SectionLabel('Your children'),
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
                const SizedBox(height: 8),
                const SectionLabel('Shortcuts'),
                if (child != null) ...[
                  _DashboardCard(
                    icon: Icons.fact_check_outlined,
                    color: status.of(StatusKind.present),
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
                    color: status.of(StatusKind.bus),
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
                  color: DesignColors.brand,
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
                  color: DesignColors.ink3,
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

/// Horizontal pill switcher — friendlier than a dropdown for 1-4 children.
/// The switcher is a Panel-like rounded container; the selected child gets a
/// brandSoft background and a brand border.
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
    return SingleChildScrollView(
      scrollDirection: Axis.horizontal,
      child: DecoratedBox(
        decoration: BoxDecoration(
          color: Colors.white,
          borderRadius: BorderRadius.circular(999),
          border: Border.all(color: DesignColors.line),
          boxShadow: [
            BoxShadow(
              color: DesignColors.ink.withValues(alpha: 0.06),
              blurRadius: 24,
              offset: const Offset(0, 12),
            ),
          ],
        ),
        child: Padding(
          padding: const EdgeInsets.all(4),
          child: Row(
            mainAxisSize: MainAxisSize.min,
            children: [
              for (final child in children)
                _ChildPill(
                  child: child,
                  initials: _initials(child),
                  selected: selected?.id == child.id,
                  onTap: () => onSelected(child),
                ),
            ],
          ),
        ),
      ),
    );
  }
}

class _ChildPill extends StatelessWidget {
  const _ChildPill({
    required this.child,
    required this.initials,
    required this.selected,
    required this.onTap,
  });

  final ParentChild child;
  final String initials;
  final bool selected;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: onTap,
      child: Container(
        margin: const EdgeInsets.symmetric(horizontal: 2),
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 7),
        decoration: BoxDecoration(
          color: selected ? DesignColors.brandSoft : Colors.transparent,
          borderRadius: BorderRadius.circular(999),
          border: Border.all(
            color: selected ? DesignColors.brand : Colors.transparent,
            width: 1.5,
          ),
        ),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            InitialsAvatar(
              initials: initials,
              color: DesignColors.brand,
              size: 30,
            ),
            const SizedBox(width: 8),
            Text(
              child.firstName,
              style: TextStyle(
                fontSize: 13,
                fontWeight: selected ? FontWeight.w700 : FontWeight.w500,
                color: selected ? DesignColors.brandInk : DesignColors.ink2,
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _DashboardCard extends StatelessWidget {
  const _DashboardCard({
    required this.icon,
    required this.color,
    required this.title,
    required this.subtitle,
    required this.onTap,
  });

  final IconData icon;
  final Color color;
  final String title;
  final String subtitle;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return Panel(
      onTap: onTap,
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
      child: Row(
        children: [
          Container(
            width: 48,
            height: 48,
            decoration: BoxDecoration(
              color: color.withValues(alpha: 0.12),
              borderRadius: BorderRadius.circular(14),
            ),
            child: Icon(icon, color: color),
          ),
          const SizedBox(width: 14),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  title,
                  style: const TextStyle(
                    fontWeight: FontWeight.w700,
                    fontSize: 15,
                  ),
                ),
                const SizedBox(height: 2),
                Text(
                  subtitle,
                  style: const TextStyle(
                    fontSize: 13,
                    color: DesignColors.ink2,
                  ),
                ),
              ],
            ),
          ),
          const Icon(Icons.chevron_right, color: DesignColors.ink3),
        ],
      ),
    );
  }
}
