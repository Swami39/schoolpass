import 'package:flutter/material.dart';
import 'package:schoolpass_design/schoolpass_design.dart' as design;

import '../api/teacher_errors.dart';
import '../app/teacher_app_controller.dart';
import '../attendance/teacher_attendance_models.dart';
import '../classes/teacher_class_models.dart';
import '../classes/teacher_student_models.dart';
import 'format.dart';
import 'teacher_widgets.dart';

const _statuses = ['present', 'late', 'absent', 'excused'];

/// Initials for the design-system avatar (mirrors teacher_widgets' rule).
String _initialsOf(String name) {
  final parts = name.trim().split(RegExp(r'\s+')).where((p) => p.isNotEmpty).toList();
  if (parts.isEmpty) return '?';
  if (parts.length == 1) return parts.first.substring(0, 1).toUpperCase();
  return '${parts.first.substring(0, 1)}${parts.last.substring(0, 1)}'.toUpperCase();
}

/// Stable brand-tinted avatar colour per student name.
Color _avatarColor(String name) {
  const palette = [
    design.DesignColors.brand,
    design.DesignColors.brand2,
    design.DesignColors.brandInk,
  ];
  var hash = 0;
  for (final c in name.codeUnits) {
    hash = (hash * 31 + c) & 0x7fffffff;
  }
  return palette[hash % palette.length];
}

/// Status pill for a record (or the unmarked state).
Widget _statusPill(TeacherAttendanceRecord? record) {
  if (record == null) {
    return const design.StatusPill(
      kind: design.StatusKind.neutral,
      label: 'Not marked',
    );
  }
  final at = record.entryAt;
  final time = at == null ? '' : ' \u00b7 ${formatTime(at)}';
  switch (record.status.toLowerCase()) {
    case 'present':
      return design.StatusPill(
        kind: design.StatusKind.present,
        label: 'Present$time',
      );
    case 'late':
      return design.StatusPill(
        kind: design.StatusKind.late,
        label: 'Late$time',
      );
    case 'absent':
      return const design.StatusPill(
        kind: design.StatusKind.absent,
        label: 'Absent',
      );
    case 'excused':
      return const design.StatusPill(
        kind: design.StatusKind.bus,
        label: 'Excused',
      );
    case 'manual':
      return const design.StatusPill(
        kind: design.StatusKind.neutral,
        label: 'Manual',
      );
    default:
      return design.StatusPill(
        kind: design.StatusKind.neutral,
        label: prettifyLabel(record.status),
      );
  }
}

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
    return Scaffold(
      appBar: AppBar(title: Text('Attendance \u00b7 ${widget.clazz.displayLabel}')),
      body: RefreshIndicator(
        onRefresh: _load,
        child: _loading
            ? const LoadingView()
            : ListView(
                padding: const EdgeInsets.all(16),
                children: [
                  _RegisterHeader(
                    classLabel: widget.clazz.displayLabel,
                    present: _countFor('present'),
                    late: _countFor('late'),
                    absent: _countFor('absent'),
                    total: _students.length,
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
                    )
                  else ...[
                    const design.SectionLabel('Roster'),
                    for (final student in _students)
                      _StudentAttendanceTile(
                        student: student,
                        record: _records[student.id],
                        saving: _savingIds.contains(student.id),
                        onMark: _mark,
                      ),
                  ],
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
                  label: Text('Finish \u00b7 $_markedCount of ${_students.length} marked'),
                ),
              ),
            ),
    );
  }
}

/// Register summary header: class title, attendance-rate ring and
/// present/late/absent tallies.
class _RegisterHeader extends StatelessWidget {
  const _RegisterHeader({
    required this.classLabel,
    required this.present,
    required this.late,
    required this.absent,
    required this.total,
  });

  final String classLabel;
  final int present;
  final int late;
  final int absent;
  final int total;

  double get _rate => total == 0 ? 0 : (present + late) / total;

  @override
  Widget build(BuildContext context) {
    return design.Panel(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            crossAxisAlignment: CrossAxisAlignment.center,
            children: [
              Expanded(
                child: design.DesignAppBarTitle(
                  classLabel,
                  subtitle: formatDayYear(DateTime.now()),
                ),
              ),
              design.StatRing(fraction: _rate, label: 'Present', size: 76),
            ],
          ),
          const SizedBox(height: 14),
          Row(
            children: [
              Expanded(
                child: design.Tally(
                  count: present,
                  label: 'Present',
                  kind: design.StatusKind.present,
                ),
              ),
              const SizedBox(width: 8),
              Expanded(
                child: design.Tally(
                  count: late,
                  label: 'Late',
                  kind: design.StatusKind.late,
                ),
              ),
              const SizedBox(width: 8),
              Expanded(
                child: design.Tally(
                  count: absent,
                  label: 'Absent',
                  kind: design.StatusKind.absent,
                ),
              ),
            ],
          ),
        ],
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
    return Padding(
      padding: const EdgeInsets.only(bottom: 10),
      child: design.Panel(
        padding: const EdgeInsets.all(14),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                design.InitialsAvatar(
                  initials: _initialsOf(student.displayName),
                  color: _avatarColor(student.displayName),
                  size: 44,
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        student.displayName,
                        style: Theme.of(context).textTheme.titleSmall?.copyWith(
                          fontWeight: FontWeight.w600,
                        ),
                      ),
                      const SizedBox(height: 2),
                      Text(
                        'Adm ${student.admissionNo}',
                        style: design.DesignTypography.mono(
                          size: 12,
                          color: design.DesignColors.ink3,
                        ),
                      ),
                      if (record != null)
                        Text(
                          'via ${prettifyLabel(record!.source)}',
                          style: Theme.of(context).textTheme.bodySmall?.copyWith(
                                color: design.DesignColors.ink3,
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
                  _statusPill(record),
              ],
            ),
            const SizedBox(height: 12),
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