import 'package:flutter/material.dart';

import '../app/teacher_app_controller.dart';
import '../classes/teacher_class_models.dart';

class HomeScreen extends StatelessWidget {
  const HomeScreen({required this.controller, super.key});

  final TeacherAppController controller;

  @override
  Widget build(BuildContext context) {
    return AnimatedBuilder(
      animation: controller,
      builder: (context, _) {
        final selected = controller.selectedClass;
        return Scaffold(
          appBar: AppBar(
            title: const Text('My classes'),
            actions: [
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
                if (controller.loadingClasses)
                  const Center(child: Padding(padding: EdgeInsets.all(24), child: CircularProgressIndicator()))
                else if (controller.classes.isEmpty)
                  const Text('No class assignments for this account.')
                else
                  ...controller.classes.map((c) => _ClassCard(
                        clazz: c,
                        selected: selected?.sectionId == c.sectionId,
                        onTap: () => controller.selectClass(c),
                      )),
                if (controller.errorMessage != null) ...[
                  const SizedBox(height: 8),
                  Text(controller.errorMessage!, style: TextStyle(color: Theme.of(context).colorScheme.error)),
                ],
                if (selected != null) ...[
                  const SizedBox(height: 24),
                  Text('Class hub', style: Theme.of(context).textTheme.titleMedium),
                  const SizedBox(height: 8),
                  _HubTile(icon: Icons.people_outline, label: 'Students'),
                  _HubTile(icon: Icons.fact_check_outlined, label: 'Attendance'),
                  _HubTile(icon: Icons.schedule_outlined, label: 'Timetable'),
                  _HubTile(icon: Icons.grade_outlined, label: 'Results'),
                  _HubTile(icon: Icons.message_outlined, label: 'Messages'),
                  _HubTile(icon: Icons.notifications_outlined, label: 'Notifications'),
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
  const _ClassCard({required this.clazz, required this.selected, required this.onTap});

  final TeacherClassAssignment clazz;
  final bool selected;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return Card(
      color: selected ? Theme.of(context).colorScheme.primaryContainer : null,
      child: ListTile(
        onTap: onTap,
        title: Text(clazz.displayLabel),
        subtitle: Text(
          [
            if (clazz.subjectName != null) clazz.subjectName!,
            '${clazz.studentCount} students',
            'Today: ${clazz.todayPresentCount} present, ${clazz.todayAbsentCount} absent',
          ].join(' · '),
        ),
        trailing: selected ? const Icon(Icons.check_circle) : null,
      ),
    );
  }
}

class _HubTile extends StatelessWidget {
  const _HubTile({required this.icon, required this.label});

  final IconData icon;
  final String label;

  @override
  Widget build(BuildContext context) {
    return ListTile(leading: Icon(icon), title: Text(label));
  }
}
