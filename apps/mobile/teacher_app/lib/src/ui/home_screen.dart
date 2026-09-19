import 'package:flutter/material.dart';

import '../app/teacher_app_controller.dart';
import '../classes/teacher_class_models.dart';
import 'class_hub_screen.dart';
import 'notifications_screen.dart';

class HomeScreen extends StatelessWidget {
  const HomeScreen({required this.controller, super.key});

  final TeacherAppController controller;

  @override
  Widget build(BuildContext context) {
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
                Text('Assigned classes', style: Theme.of(context).textTheme.titleMedium),
                const SizedBox(height: 8),
                if (controller.loadingClasses)
                  const Center(child: Padding(padding: EdgeInsets.all(24), child: CircularProgressIndicator()))
                else if (controller.classes.isEmpty)
                  const Text('No class assignments for this account.')
                else
                  ...controller.classes.map((c) => _ClassCard(
                        clazz: c,
                        onOpen: () => Navigator.of(context).push(
                          MaterialPageRoute<void>(
                            builder: (_) => ClassHubScreen(controller: controller, clazz: c),
                          ),
                        ),
                      )),
                if (controller.errorMessage != null) ...[
                  const SizedBox(height: 8),
                  Text(controller.errorMessage!, style: TextStyle(color: Theme.of(context).colorScheme.error)),
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
  const _ClassCard({required this.clazz, required this.onOpen});

  final TeacherClassAssignment clazz;
  final VoidCallback onOpen;

  @override
  Widget build(BuildContext context) {
    return Card(
      child: ListTile(
        onTap: onOpen,
        title: Text(clazz.displayLabel),
        subtitle: Text(
          [
            if (clazz.subjectName != null) clazz.subjectName!,
            '${clazz.studentCount} students',
            'Today: ${clazz.todayPresentCount} present, ${clazz.todayAbsentCount} absent',
          ].join(' · '),
        ),
        trailing: const Icon(Icons.chevron_right),
      ),
    );
  }
}
