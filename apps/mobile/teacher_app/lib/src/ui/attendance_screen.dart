import 'package:flutter/material.dart';

import '../api/teacher_errors.dart';
import '../app/teacher_app_controller.dart';
import '../attendance/teacher_attendance_models.dart';
import '../classes/teacher_class_models.dart';
import '../classes/teacher_student_models.dart';

class AttendanceScreen extends StatefulWidget {
  const AttendanceScreen({required this.controller, required this.clazz, super.key});

  final TeacherAppController controller;
  final TeacherClassAssignment clazz;

  @override
  State<AttendanceScreen> createState() => _AttendanceScreenState();
}

class _AttendanceScreenState extends State<AttendanceScreen> {
  bool _loading = true;
  String? _error;
  List<TeacherStudent> _students = const [];
  Map<String, TeacherAttendanceRecord> _records = {};

  String get _today => DateTime.now().toIso8601String().split('T').first;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final students = await widget.controller.deps.classesApi.fetchStudents(widget.clazz.sectionId);
      final records = await widget.controller.deps.attendanceApi.fetchAttendance(
        sectionId: widget.clazz.sectionId,
        onDate: _today,
      );
      if (!mounted) return;
      setState(() {
        _students = students;
        _records = {for (final r in records) r.studentId: r};
        _loading = false;
      });
    } on TeacherUnauthorized {
      await widget.controller.logout();
    } on TeacherNotFound {
      if (!mounted) return;
      setState(() {
        _error = 'You are not assigned to this class.';
        _loading = false;
      });
    } catch (_) {
      if (!mounted) return;
      setState(() {
        _error = 'Could not load attendance.';
        _loading = false;
      });
    }
  }

  Future<void> _mark(TeacherStudent student, String status) async {
    try {
      final record = await widget.controller.deps.attendanceApi.markAttendance(
        sectionId: widget.clazz.sectionId,
        onDate: _today,
        studentId: student.id,
        status: status,
      );
      if (!mounted) return;
      setState(() => _records[student.id] = record);
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('${student.displayName}: $status')),
        );
      }
    } on TeacherUnauthorized {
      await widget.controller.logout();
    } catch (_) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Could not save attendance.')),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: Text('Attendance · ${widget.clazz.displayLabel}')),
      body: RefreshIndicator(
        onRefresh: _load,
        child: _loading
            ? ListView(children: const [SizedBox(height: 200), Center(child: CircularProgressIndicator())])
            : ListView(
                padding: const EdgeInsets.all(16),
                children: [
                  Text('Date: $_today', style: Theme.of(context).textTheme.titleSmall),
                  if (_error != null) Text(_error!, style: TextStyle(color: Theme.of(context).colorScheme.error)),
                  if (_students.isEmpty && _error == null) const Text('No students.'),
                  for (final student in _students)
                    _StudentAttendanceTile(
                      student: student,
                      record: _records[student.id],
                      onMark: _mark,
                    ),
                ],
              ),
      ),
    );
  }
}

class _StudentAttendanceTile extends StatelessWidget {
  const _StudentAttendanceTile({
    required this.student,
    required this.record,
    required this.onMark,
  });

  final TeacherStudent student;
  final TeacherAttendanceRecord? record;
  final Future<void> Function(TeacherStudent student, String status) onMark;

  @override
  Widget build(BuildContext context) {
    final status = record?.status ?? 'not marked';
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(12),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(student.displayName, style: Theme.of(context).textTheme.titleMedium),
            Text('Status: $status${record != null ? ' (${record!.source})' : ''}'),
            const SizedBox(height: 8),
            Wrap(
              spacing: 8,
              children: [
                for (final s in const ['present', 'late', 'absent', 'excused'])
                  OutlinedButton(onPressed: () => onMark(student, s), child: Text(s)),
              ],
            ),
          ],
        ),
      ),
    );
  }
}
