import 'package:flutter/material.dart';

import '../api/teacher_errors.dart';
import '../app/teacher_app_controller.dart';
import '../classes/teacher_class_models.dart';
import '../classes/teacher_student_models.dart';
import '../results/teacher_results_models.dart';

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
    try {
      final updated = await widget.controller.deps.resultsApi.upsertMark(
        assessmentId: widget.assessment.id,
        studentId: student.id,
        marks: parsed,
      );
      if (!mounted) return;
      setState(() => _marks[student.id] = updated.marks);
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Saved ${student.displayName}')),
      );
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
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: Text('${widget.assessment.code} marks')),
      body: _loading
          ? const Center(child: CircularProgressIndicator())
          : ListView(
              padding: const EdgeInsets.all(16),
              children: [
                Text('Maximum: ${widget.assessment.maxMarks}'),
                if (_error != null) Text(_error!, style: TextStyle(color: Theme.of(context).colorScheme.error)),
                for (final student in _students)
                  _MarkRow(
                    student: student,
                    initial: _marks[student.id]?.toString() ?? '',
                    onSave: (v) => _save(student, v),
                  ),
              ],
            ),
    );
  }
}

class _MarkRow extends StatefulWidget {
  const _MarkRow({required this.student, required this.initial, required this.onSave});

  final TeacherStudent student;
  final String initial;
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
    return ListTile(
      title: Text(widget.student.displayName),
      subtitle: TextField(
        controller: _controller,
        keyboardType: TextInputType.number,
        decoration: const InputDecoration(labelText: 'Marks'),
      ),
      trailing: IconButton(
        icon: const Icon(Icons.save_outlined),
        onPressed: () => widget.onSave(_controller.text),
      ),
    );
  }
}
