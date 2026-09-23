import 'package:flutter/material.dart';

import '../app/teacher_app_controller.dart';
import '../classes/teacher_class_models.dart';
import 'attendance_screen.dart';
import 'messages_screen.dart';
import 'nfc_attendance_screen.dart';
import 'results_screen.dart';
import 'students_screen.dart';
import 'teacher_widgets.dart';
import 'timetable_screen.dart';

class ClassHubScreen extends StatelessWidget {
  const ClassHubScreen({required this.controller, required this.clazz, super.key});

  final TeacherAppController controller;
  final TeacherClassAssignment clazz;

  void _open(BuildContext context, Widget screen) {
    Navigator.of(context).push(
      MaterialPageRoute<void>(builder: (_) => screen),
    );
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Scaffold(
      appBar: AppBar(title: Text(clazz.displayLabel)),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          Text(
            '${clazz.studentCount} students'
            '${clazz.subjectName == null ? '' : ' · ${clazz.subjectName}'}',
            style: theme.textTheme.bodyMedium?.copyWith(
              color: theme.colorScheme.onSurfaceVariant,
            ),
          ),
          const SizedBox(height: 16),
          const SectionHeader('Daily work'),
          TeacherSectionCard(
            icon: Icons.fact_check_outlined,
            title: 'Attendance',
            subtitle: 'Mark present, late, absent or excused',
            onTap: () => _open(
              context,
              AttendanceScreen(controller: controller, clazz: clazz),
            ),
          ),
          const SizedBox(height: 8),
          TeacherSectionCard(
            icon: Icons.nfc,
            title: 'NFC attendance',
            subtitle: 'Tap student cards to record scans',
            onTap: () => _open(
              context,
              NfcAttendanceScreen(controller: controller, clazz: clazz),
            ),
          ),
          const SizedBox(height: 8),
          TeacherSectionCard(
            icon: Icons.message_outlined,
            title: 'Messages to parents',
            subtitle: 'Send updates to guardians',
            onTap: () => _open(
              context,
              MessagesScreen(controller: controller, clazz: clazz),
            ),
          ),
          const SizedBox(height: 16),
          const SectionHeader('Class info'),
          TeacherSectionCard(
            icon: Icons.people_outline,
            title: 'Students',
            subtitle: '${clazz.studentCount} enrolled',
            onTap: () => _open(
              context,
              StudentsScreen(controller: controller, clazz: clazz),
            ),
          ),
          const SizedBox(height: 8),
          TeacherSectionCard(
            icon: Icons.schedule_outlined,
            title: 'Timetable',
            subtitle: 'Weekly periods for this class',
            onTap: () => _open(
              context,
              TimetableScreen(controller: controller, clazz: clazz),
            ),
          ),
          const SizedBox(height: 8),
          TeacherSectionCard(
            icon: Icons.grade_outlined,
            title: 'Results',
            subtitle: 'Assessments and marks',
            onTap: () => _open(
              context,
              ResultsScreen(controller: controller, clazz: clazz),
            ),
          ),
        ],
      ),
    );
  }
}
