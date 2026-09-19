import 'package:flutter/material.dart';

import '../app/teacher_app_controller.dart';
import '../classes/teacher_class_models.dart';
import 'attendance_screen.dart';
import 'messages_screen.dart';
import 'nfc_attendance_screen.dart';
import 'results_screen.dart';
import 'students_screen.dart';
import 'timetable_screen.dart';

class ClassHubScreen extends StatelessWidget {
  const ClassHubScreen({required this.controller, required this.clazz, super.key});

  final TeacherAppController controller;
  final TeacherClassAssignment clazz;

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: Text(clazz.displayLabel)),
      body: ListView(
        children: [
          ListTile(
            leading: const Icon(Icons.people_outline),
            title: const Text('Students'),
            onTap: () => Navigator.of(context).push(
              MaterialPageRoute<void>(
                builder: (_) => StudentsScreen(controller: controller, clazz: clazz),
              ),
            ),
          ),
          ListTile(
            leading: const Icon(Icons.fact_check_outlined),
            title: const Text('Attendance'),
            onTap: () => Navigator.of(context).push(
              MaterialPageRoute<void>(
                builder: (_) => AttendanceScreen(controller: controller, clazz: clazz),
              ),
            ),
          ),
          ListTile(
            leading: const Icon(Icons.nfc),
            title: const Text('NFC attendance'),
            onTap: () => Navigator.of(context).push(
              MaterialPageRoute<void>(
                builder: (_) => NfcAttendanceScreen(controller: controller, clazz: clazz),
              ),
            ),
          ),
          ListTile(
            leading: const Icon(Icons.schedule_outlined),
            title: const Text('Timetable'),
            onTap: () => Navigator.of(context).push(
              MaterialPageRoute<void>(
                builder: (_) => TimetableScreen(controller: controller, clazz: clazz),
              ),
            ),
          ),
          ListTile(
            leading: const Icon(Icons.grade_outlined),
            title: const Text('Results'),
            onTap: () => Navigator.of(context).push(
              MaterialPageRoute<void>(
                builder: (_) => ResultsScreen(controller: controller, clazz: clazz),
              ),
            ),
          ),
          ListTile(
            leading: const Icon(Icons.message_outlined),
            title: const Text('Messages to parents'),
            onTap: () => Navigator.of(context).push(
              MaterialPageRoute<void>(
                builder: (_) => MessagesScreen(controller: controller, clazz: clazz),
              ),
            ),
          ),
        ],
      ),
    );
  }
}
