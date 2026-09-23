import 'package:flutter/material.dart';

import '../app/teacher_app_controller.dart';
import '../classes/teacher_class_models.dart';
import 'attendance_screen.dart';
import 'class_hub_screen.dart';
import 'format.dart';
import 'notifications_screen.dart';
import 'teacher_widgets.dart';

class HomeScreen extends StatelessWidget {
  const HomeScreen({required this.controller, super.key});

  final TeacherAppController controller;

  void _openClass(BuildContext context, TeacherClassAssignment clazz) {
    controller.selectClass(clazz);
    Navigator.of(context).push(
      MaterialPageRoute<void>(
        builder: (_) => ClassHubScreen(controller: controller, clazz: clazz),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return AnimatedBuilder(
      animation: controller,
      builder: (context, _) {
        return Scaffold(
          appBar: AppBar(
            title: const Text('Teacher dashboard'),
            actions: [
              IconButton(
                tooltip: 'Notifications',
                icon: const Icon(Icons.notifications_outlined),
                onPressed: () => Navigator.of(context).push(
                  MaterialPageRoute<void>(
                    builder: (_) => NotificationsScreen(controller: controller),
                  ),
                ),
              ),
              IconButton(
                onPressed: controller.logout,
                tooltip: 'Sign out',
                icon: const Icon(Icons.logout),
              ),
            ],
          ),
          body: RefreshIndicator(
            onRefresh: controller.refreshClasses,
            child: ListView(
              padding: const EdgeInsets.all(16),
              children: [
                Text(
                  '${dayGreeting()}, Teacher',
                  style: theme.textTheme.headlineSmall?.copyWith(
                    fontWeight: FontWeight.w700,
                  ),
                ),
                const SizedBox(height: 4),
                Text(
                  formatDayYear(DateTime.now()),
                  style: theme.textTheme.bodyMedium?.copyWith(
                    color: theme.colorScheme.onSurfaceVariant,
                  ),
                ),
                const SizedBox(height: 16),
                if (controller.loadingClasses)
                  const LoadingView()
                else if (controller.classes.isEmpty)
                  const EmptyState(
                    icon: Icons.class_outlined,
                    title: 'No class assignments',
                    subtitle:
                        'No classes are assigned to this account yet. Ask your school admin to assign classes to you.',
                  )
                else ...[
                  const SectionHeader('My classes'),
                  for (final clazz in controller.classes) ...[
                    _ClassCard(
                      clazz: clazz,
                      onOpen: () => _openClass(context, clazz),
                      onTakeAttendance: () {
                        controller.selectClass(clazz);
                        Navigator.of(context).push(
                          MaterialPageRoute<void>(
                            builder: (_) => AttendanceScreen(
                              controller: controller,
                              clazz: clazz,
                            ),
                          ),
                        );
                      },
                    ),
                    const SizedBox(height: 12),
                  ],
                ],
                if (controller.errorMessage != null) ...[
                  const SizedBox(height: 8),
                  ErrorBanner(
                    message: controller.errorMessage!,
                    onRetry: controller.refreshClasses,
                  ),
                ],
              ],
            ),
          ),
        );
      },
    );
  }
}

class _ClassCard extends StatelessWidget {
  const _ClassCard({
    required this.clazz,
    required this.onOpen,
    required this.onTakeAttendance,
  });

  final TeacherClassAssignment clazz;
  final VoidCallback onOpen;
  final VoidCallback onTakeAttendance;

  int get _pending {
    final pending =
        clazz.studentCount - clazz.todayPresentCount - clazz.todayAbsentCount;
    return pending < 0 ? 0 : pending;
  }

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            InkWell(
              onTap: onOpen,
              borderRadius: BorderRadius.circular(12),
              child: Row(
                children: [
                  Container(
                    width: 48,
                    height: 48,
                    decoration: BoxDecoration(
                      color: scheme.primaryContainer,
                      borderRadius: BorderRadius.circular(14),
                    ),
                    child: Icon(
                      Icons.class_outlined,
                      color: scheme.onPrimaryContainer,
                    ),
                  ),
                  const SizedBox(width: 12),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          clazz.displayLabel,
                          style: const TextStyle(
                            fontWeight: FontWeight.w700,
                            fontSize: 16,
                          ),
                        ),
                        const SizedBox(height: 2),
                        Text(
                          [
                            if (clazz.subjectName != null) clazz.subjectName!,
                            '${clazz.studentCount} students',
                          ].join(' · '),
                          style: TextStyle(
                            color: scheme.onSurfaceVariant,
                          ),
                        ),
                      ],
                    ),
                  ),
                  Icon(Icons.chevron_right, color: scheme.onSurfaceVariant),
                ],
              ),
            ),
            const SizedBox(height: 12),
            const Divider(height: 1),
            const SizedBox(height: 12),
            Row(
              children: [
                Expanded(
                  child: _StatChip(
                    icon: Icons.check_circle_outline,
                    color: const Color(0xFF15803D),
                    value: '${clazz.todayPresentCount}',
                    label: 'present',
                  ),
                ),
                Expanded(
                  child: _StatChip(
                    icon: Icons.cancel_outlined,
                    color: scheme.error,
                    value: '${clazz.todayAbsentCount}',
                    label: 'absent',
                  ),
                ),
                Expanded(
                  child: _StatChip(
                    icon: Icons.pending_outlined,
                    color: scheme.onSurfaceVariant,
                    value: '$_pending',
                    label: 'pending',
                  ),
                ),
              ],
            ),
            const SizedBox(height: 12),
            SizedBox(
              width: double.infinity,
              child: FilledButton.tonalIcon(
                onPressed: onTakeAttendance,
                icon: const Icon(Icons.fact_check_outlined),
                label: const Text('Take attendance'),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _StatChip extends StatelessWidget {
  const _StatChip({
    required this.icon,
    required this.color,
    required this.value,
    required this.label,
  });

  final IconData icon;
  final Color color;
  final String value;
  final String label;

  @override
  Widget build(BuildContext context) {
    return Column(
      children: [
        Icon(icon, color: color),
        const SizedBox(height: 4),
        Text(
          value,
          style: TextStyle(
            fontWeight: FontWeight.w700,
            fontSize: 16,
            color: color,
          ),
        ),
        Text(
          label,
          style: Theme.of(context).textTheme.bodySmall?.copyWith(
                color: Theme.of(context).colorScheme.onSurfaceVariant,
              ),
        ),
      ],
    );
  }
}
