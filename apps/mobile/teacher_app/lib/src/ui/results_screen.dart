import 'package:flutter/material.dart';

import '../api/teacher_errors.dart';
import '../app/teacher_app_controller.dart';
import '../classes/teacher_class_models.dart';
import '../results/teacher_results_models.dart';
import 'marks_screen.dart';

class ResultsScreen extends StatefulWidget {
  const ResultsScreen({required this.controller, required this.clazz, super.key});

  final TeacherAppController controller;
  final TeacherClassAssignment clazz;

  @override
  State<ResultsScreen> createState() => _ResultsScreenState();
}

class _ResultsScreenState extends State<ResultsScreen> {
  bool _loading = true;
  String? _error;
  List<TeacherAssessment> _items = const [];

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
      final items = await widget.controller.deps.resultsApi.fetchAssessments(widget.clazz.sectionId);
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
        _error = 'Class not assigned.';
        _loading = false;
      });
    } catch (_) {
      if (!mounted) return;
      setState(() {
        _error = 'Could not load assessments.';
        _loading = false;
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: Text('Assessments · ${widget.clazz.displayLabel}')),
      body: RefreshIndicator(
        onRefresh: _load,
        child: _loading
            ? ListView(children: const [SizedBox(height: 200), Center(child: CircularProgressIndicator())])
            : ListView(
                padding: const EdgeInsets.all(16),
                children: [
                  if (_error != null) Text(_error!, style: TextStyle(color: Theme.of(context).colorScheme.error)),
                  if (_items.isEmpty && _error == null) const Text('No assessments.'),
                  for (final a in _items)
                    ListTile(
                      title: Text('${a.code} · ${a.name}'),
                      subtitle: Text('Max ${a.maxMarks} marks'),
                      trailing: const Icon(Icons.chevron_right),
                      onTap: () => Navigator.of(context).push(
                        MaterialPageRoute<void>(
                          builder: (_) => MarksScreen(
                            controller: widget.controller,
                            clazz: widget.clazz,
                            assessment: a,
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
