import 'package:flutter/material.dart';

import '../api/teacher_errors.dart';
import '../app/teacher_app_controller.dart';
import '../classes/teacher_class_models.dart';
import '../classes/teacher_student_models.dart';
import 'teacher_widgets.dart';

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
  String _query = '';

  List<TeacherStudent> get _filtered {
    if (_query.isEmpty) return _items;
    final q = _query.toLowerCase();
    return _items
        .where((s) =>
            s.displayName.toLowerCase().contains(q) ||
            s.admissionNo.toLowerCase().contains(q))
        .toList();
  }

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
    final theme = Theme.of(context);
    return Scaffold(
      appBar: AppBar(title: Text('${widget.clazz.displayLabel} students')),
      body: RefreshIndicator(
        onRefresh: _load,
        child: _loading
            ? const LoadingView()
            : ListView(
                padding: const EdgeInsets.all(16),
                children: [
                  if (_error != null) ...[
                    ErrorBanner(message: _error!, onRetry: _load),
                    const SizedBox(height: 8),
                  ],
                  if (_items.isNotEmpty)
                    TextField(
                      decoration: const InputDecoration(
                        labelText: 'Search students',
                        prefixIcon: Icon(Icons.search),
                      ),
                      onChanged: (v) => setState(() => _query = v.trim()),
                    ),
                  const SizedBox(height: 8),
                  if (_items.isEmpty && _error == null)
                    const EmptyState(
                      icon: Icons.people_outline,
                      title: 'No students enrolled',
                      subtitle: 'This class has no students yet.',
                    )
                  else if (_filtered.isEmpty)
                    const EmptyState(
                      icon: Icons.search_off_outlined,
                      title: 'No matches',
                      subtitle: 'Try a different name or admission number.',
                    )
                  else
                    for (final student in _filtered)
                      Padding(
                        padding: const EdgeInsets.only(bottom: 8),
                        child: Card(
                          child: ListTile(
                            leading: InitialsAvatar(name: student.displayName),
                            title: Text(
                              student.displayName,
                              style: const TextStyle(fontWeight: FontWeight.w600),
                            ),
                            subtitle: Text('Adm. no. ${student.admissionNo}'),
                            trailing: student.status.toLowerCase() == 'active'
                                ? StatusChip(
                                    label: 'Active',
                                    color: const Color(0xFF15803D),
                                    icon: Icons.check_circle_outline,
                                  )
                                : StatusChip(
                                    label: student.status,
                                    color: theme.colorScheme.onSurfaceVariant,
                                  ),
                          ),
                        ),
                      ),
                ],
              ),
      ),
    );
  }
}
