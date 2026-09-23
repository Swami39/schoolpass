import 'package:flutter/material.dart';

import '../api/teacher_errors.dart';
import '../app/teacher_app_controller.dart';
import '../classes/teacher_class_models.dart';
import '../classes/teacher_student_models.dart';
import '../results/teacher_results_models.dart';
import 'teacher_widgets.dart';

class MarksScreen extends StatefulWidget {
  const MarksScreen({
    required this.controller,
    required this.clazz,
    required this.assessment,
    super.key,
  });

  final TeacherAppController controller;
  final TeacherClassAssignment clazz;
  final TeacherAssessment assessment;

  @override
  State<MarksScreen> createState() => _MarksScreenState();
}

class _MarksScreenState extends State<MarksScreen> {
  bool _loading = true;
  String? _error;
  List<TeacherStudent> _students = const [];
  Map<String, int?> _marks = {};
  final Set<String> _savingIds = {};

  int get _recordedCount => _marks.values.where((m) => m != null).length;

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
      final sheet = await widget.controller.deps.resultsApi.fetchMarks(widget.assessment.id);
      if (!mounted) return;
      setState(() {
        _students = students;
        _marks = {for (final m in sheet.items) m.studentId: m.marks};
        _loading = false;
      });
    } on TeacherUnauthorized {
      await widget.controller.logout();
    } catch (_) {
      if (!mounted) return;
      setState(() {
        _error = 'Could not load marks.';
        _loading = false;
      });
    }
  }

  Future<void> _save(TeacherStudent student, String raw) async {
    final parsed = int.tryParse(raw.trim());
    if (parsed == null) return;
    if (_savingIds.contains(student.id)) return;
    setState(() => _savingIds.add(student.id));
    try {
      final updated = await widget.controller.deps.resultsApi.upsertMark(
        assessmentId: widget.assessment.id,
        studentId: student.id,
        marks: parsed,
      );
      if (!mounted) return;
      setState(() => _marks[student.id] = updated.marks);
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Saved ${student.displayName}: ${updated.marks}')),
        );
      }
    } on TeacherUnauthorized {
      await widget.controller.logout();
    } on TeacherNotFound {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Not authorized for this assessment.')),
      );
    } catch (_) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Invalid marks or save failed.')),
      );
    } finally {
      if (mounted) setState(() => _savingIds.remove(student.id));
    }
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final scheme = theme.colorScheme;
    return Scaffold(
      appBar: AppBar(title: Text('${widget.assessment.code} marks')),
      body: _loading
          ? const Center(child: CircularProgressIndicator())
          : ListView(
              padding: const EdgeInsets.all(16),
              children: [
                Card(
                  color: scheme.primaryContainer,
                  child: Padding(
                    padding: const EdgeInsets.all(16),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          widget.assessment.name,
                          style: theme.textTheme.titleMedium?.copyWith(
                            fontWeight: FontWeight.w700,
                            color: scheme.onPrimaryContainer,
                          ),
                        ),
                        const SizedBox(height: 4),
                        Text(
                          'Maximum ${widget.assessment.maxMarks} marks · '
                          '$_recordedCount of ${_students.length} recorded',
                          style: theme.textTheme.bodyMedium?.copyWith(
                            color: scheme.onPrimaryContainer,
                          ),
                        ),
                      ],
                    ),
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
                    subtitle: 'There is nobody to mark for this assessment.',
                  ),
                for (final student in _students)
                  _MarkRow(
                    student: student,
                    initial: _marks[student.id]?.toString() ?? '',
                    maxMarks: widget.assessment.maxMarks,
                    saving: _savingIds.contains(student.id),
                    onSave: (v) => _save(student, v),
                  ),
              ],
            ),
    );
  }
}

class _MarkRow extends StatefulWidget {
  const _MarkRow({
    required this.student,
    required this.initial,
    required this.maxMarks,
    required this.saving,
    required this.onSave,
  });

  final TeacherStudent student;
  final String initial;
  final int maxMarks;
  final bool saving;
  final Future<void> Function(String value) onSave;

  @override
  State<_MarkRow> createState() => _MarkRowState();
}

class _MarkRowState extends State<_MarkRow> {
  late final TextEditingController _controller;

  @override
  void initState() {
    super.initState();
    _controller = TextEditingController(text: widget.initial);
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final hasMark = widget.initial.isNotEmpty;
    return Padding(
      padding: const EdgeInsets.only(bottom: 8),
      child: Card(
        child: Padding(
          padding: const EdgeInsets.all(12),
          child: Row(
            children: [
              InitialsAvatar(name: widget.student.displayName, radius: 18),
              const SizedBox(width: 12),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      widget.student.displayName,
                      style: const TextStyle(fontWeight: FontWeight.w600),
                    ),
                    if (hasMark)
                      StatusChip(
                        label: '${widget.initial} / ${widget.maxMarks}',
                        color: const Color(0xFF15803D),
                        icon: Icons.check_circle_outline,
                      ),
                  ],
                ),
              ),
              SizedBox(
                width: 96,
                child: TextField(
                  controller: _controller,
                  keyboardType: TextInputType.number,
                  decoration: const InputDecoration(labelText: 'Marks'),
                  onSubmitted: widget.onSave,
                ),
              ),
              const SizedBox(width: 8),
              widget.saving
                  ? const SizedBox(
                      width: 20,
                      height: 20,
                      child: CircularProgressIndicator(strokeWidth: 2),
                    )
                  : IconButton.filledTonal(
                      tooltip: 'Save marks',
                      icon: const Icon(Icons.check),
                      onPressed: () => widget.onSave(_controller.text),
                    ),
            ],
          ),
        ),
      ),
    );
  }
}
