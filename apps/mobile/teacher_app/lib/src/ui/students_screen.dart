import 'package:flutter/material.dart';

import '../api/teacher_errors.dart';
import '../app/teacher_app_controller.dart';
import '../classes/teacher_class_models.dart';
import '../classes/teacher_student_models.dart';

class StudentsScreen extends StatefulWidget {
  const StudentsScreen({required this.controller, required this.clazz, super.key});

  final TeacherAppController controller;
  final TeacherClassAssignment clazz;

  @override
  State<StudentsScreen> createState() => _StudentsScreenState();
}

class _StudentsScreenState extends State<StudentsScreen> {
  bool _loading = true;
  String? _error;
  List<TeacherStudent> _items = const [];

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
      final items = await widget.controller.deps.classesApi.fetchStudents(widget.clazz.sectionId);
      if (!mounted) return;
      setState(() {
        _items = items;
        _loading = false;
      });
    } on TeacherUnauthorized {
      await widget.controller.logout();
    } on TeacherNotFound {
      if (!mounted) return;
      setState(() {
        _error = 'This class is not assigned to you.';
        _items = [];
        _loading = false;
      });
    } catch (_) {
      if (!mounted) return;
      setState(() {
        _error = 'Could not load students.';
        _loading = false;
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: Text('${widget.clazz.displayLabel} students')),
      body: RefreshIndicator(
        onRefresh: _load,
        child: _loading
            ? ListView(children: const [SizedBox(height: 200), Center(child: CircularProgressIndicator())])
            : ListView(
                padding: const EdgeInsets.all(16),
                children: [
                  if (_error != null) Text(_error!, style: TextStyle(color: Theme.of(context).colorScheme.error)),
                  if (_items.isEmpty && _error == null) const Text('No students enrolled.'),
                  for (final student in _items)
                    ListTile(
                      title: Text(student.displayName),
                      subtitle: Text(student.admissionNo),
                    ),
                ],
              ),
      ),
    );
  }
}
