import 'package:flutter/material.dart';

import '../api/teacher_errors.dart';
import '../app/teacher_app_controller.dart';
import '../attendance/teacher_attendance_models.dart';
import '../classes/teacher_class_models.dart';
import '../classes/teacher_student_models.dart';
import 'format.dart';
import 'teacher_widgets.dart';

const _statuses = ['present', 'late', 'absent', 'excused'];

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
  final Set<String> _savingIds = {};

  String get _today => DateTime.now().toIso8601String().split('T').first;

  int _countFor(String status) =>
      _records.values.where((r) => r.status.toLowerCase() == status).length;

  int get _markedCount => _records.length;

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
    if (_savingIds.contains(student.id)) return;
    setState(() => _savingIds.add(student.id));
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
          SnackBar(content: Text('${student.displayName}: ${prettifyLabel(status)}')),
        );
      }
    } on TeacherUnauthorized {
      await widget.controller.logout();
    } catch (_) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Could not save attendance.')),
      );
    } finally {
      if (mounted) setState(() => _savingIds.remove(student.id));
    }
  }

  Future<void> _finish() async {
    final unmarked = _students.length - _markedCount;
    final done = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('Attendance summary'),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            for (final s in _statuses)
              Padding(
                padding: const EdgeInsets.symmetric(vertical: 4),
                child: Row(
                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                  children: [
                    Text(prettifyLabel(s)),
                    Text(
                      '${_countFor(s)}',
                      style: const TextStyle(fontWeight: FontWeight.w700),
                    ),
                  ],
                ),
              ),
            if (unmarked > 0)
              Padding(
                padding: const EdgeInsets.only(top: 8),
                child: Text(
                  '$unmarked student${unmarked == 1 ? '' : 's'} still unmarked.',
                  style: TextStyle(
                    color: Theme.of(context).colorScheme.onSurfaceVariant,
                  ),
                ),
              ),
          ],
        ),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx, false), child: const Text('Keep editing')),
          FilledButton(onPressed: () => Navigator.pop(ctx, true), child: const Text('Done')),
        ],
      ),
    );
    if (done == true && mounted) Navigator.of(context).pop();
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Scaffold(
      appBar: AppBar(title: Text('Attendance · ${widget.clazz.displayLabel}')),
      body: RefreshIndicator(
        onRefresh: _load,
        child: _loading
            ? const LoadingView()
            : ListView(
                padding: const EdgeInsets.all(16),
                children: [
                  _SummaryBar(
                    present: _countFor('present'),
                    late: _countFor('late'),
                    absent: _countFor('absent'),
                    excused: _countFor('excused'),
                    total: _students.length,
                  ),
                  const SizedBox(height: 8),
                  Text(
                    formatDayYear(DateTime.now()),
                    style: theme.textTheme.titleSmall?.copyWith(
                      color: theme.colorScheme.onSurfaceVariant,
                    ),
                  ),
                  const SizedBox(height: 8),
                  if (_error != null) ...[
                    ErrorBanner(message: _error!, onRetry: _load),
                    const SizedBox(height: 8),
                  ],
                  if (_students.isEmpty && _error == null)
                    const EmptyState(
                      icon: Icons.people_outline,
                      title: 'No students enrolled',
                      subtitle: 'This class has no students yet.',
                    ),
                  for (final student in _students)
                    _StudentAttendanceTile(
                      student: student,
                      record: _records[student.id],
                      saving: _savingIds.contains(student.id),
                      onMark: _mark,
                    ),
                ],
              ),
      ),
      bottomNavigationBar: _loading || _error != null
          ? null
          : SafeArea(
              child: Padding(
                padding: const EdgeInsets.all(16),
                child: FilledButton.icon(
                  onPressed: _finish,
                  icon: const Icon(Icons.done_all),
                  label: Text('Finish · $_markedCount of ${_students.length} marked'),
                ),
              ),
            ),
    );
  }
}

class _SummaryBar extends StatelessWidget {
  const _SummaryBar({
    required this.present,
    required this.late,
    required this.absent,
    required this.excused,
    required this.total,
  });

  final int present;
  final int late;
  final int absent;
  final int excused;
  final int total;

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    return Card(
      color: scheme.primaryContainer,
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              'Today\u2019s register',
              style: TextStyle(
                fontWeight: FontWeight.w700,
                color: scheme.onPrimaryContainer,
              ),
            ),
            const SizedBox(height: 8),
            Wrap(
              spacing: 8,
              runSpacing: 8,
              children: [
                _MiniCount(label: 'Present', count: present, color: const Color(0xFF15803D)),
                _MiniCount(label: 'Late', count: late, color: const Color(0xFFB45309)),
                _MiniCount(label: 'Absent', count: absent, color: scheme.error),
                _MiniCount(label: 'Excused', count: excused, color: const Color(0xFF1D4ED8)),
                _MiniCount(label: 'Total', count: total, color: scheme.onPrimaryContainer),
              ],
            ),
          ],
        ),
      ),
    );
  }
}

class _MiniCount extends StatelessWidget {
  const _MiniCount({required this.label, required this.count, required this.color});

  final String label;
  final int count;
  final Color color;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
      decoration: BoxDecoration(
        color: Theme.of(context).colorScheme.surface.withValues(alpha: 0.7),
        borderRadius: BorderRadius.circular(999),
      ),
      child: Text(
        '$label: $count',
        style: TextStyle(color: color, fontWeight: FontWeight.w700, fontSize: 12),
      ),
    );
  }
}

class _StudentAttendanceTile extends StatelessWidget {
  const _StudentAttendanceTile({
    required this.student,
    required this.record,
    required this.saving,
    required this.onMark,
  });

  final TeacherStudent student;
  final TeacherAttendanceRecord? record;
  final bool saving;
  final Future<void> Function(TeacherStudent student, String status) onMark;

  @override
  Widget build(BuildContext context) {
    final status = record?.status ?? 'not marked';
    return Padding(
      padding: const EdgeInsets.only(bottom: 10),
      child: Card(
        child: Padding(
          padding: const EdgeInsets.all(12),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                children: [
                  InitialsAvatar(name: student.displayName, radius: 18),
                  const SizedBox(width: 10),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(student.displayName,
                            style: Theme.of(context).textTheme.titleSmall?.copyWith(
                              fontWeight: FontWeight.w600,
                            )),
                        if (record != null)
                          Text(
                            'via ${prettifyLabel(record!.source)}',
                            style: Theme.of(context).textTheme.bodySmall?.copyWith(
                                  color: Theme.of(context).colorScheme.onSurfaceVariant,
                                ),
                          ),
                      ],
                    ),
                  ),
                  if (saving)
                    const SizedBox(
                      width: 18,
                      height: 18,
                      child: CircularProgressIndicator(strokeWidth: 2),
                    )
                  else
                    attendanceStatusChip(context, status),
                ],
              ),
              const SizedBox(height: 10),
              Wrap(
                spacing: 8,
                runSpacing: 8,
                children: [
                  for (final s in _statuses)
                    _StatusButton(
                      status: s,
                      selected: record?.status.toLowerCase() == s,
                      enabled: !saving,
                      onTap: () => onMark(student, s),
                    ),
                ],
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _StatusButton extends StatelessWidget {
  const _StatusButton({
    required this.status,
    required this.selected,
    required this.enabled,
    required this.onTap,
  });

  final String status;
  final bool selected;
  final bool enabled;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final label = prettifyLabel(status);
    if (selected) {
      return FilledButton(onPressed: enabled ? onTap : null, child: Text(label));
    }
    return OutlinedButton(onPressed: enabled ? onTap : null, child: Text(label));
  }
}
