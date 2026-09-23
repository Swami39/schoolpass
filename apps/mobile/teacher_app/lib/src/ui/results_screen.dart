import 'package:flutter/material.dart';

import '../api/teacher_errors.dart';
import '../app/teacher_app_controller.dart';
import '../classes/teacher_class_models.dart';
import '../results/teacher_results_models.dart';
import 'format.dart';
import 'marks_screen.dart';
import 'teacher_widgets.dart';

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

  String _scheduledLabel(String? raw) {
    if (raw == null) return '';
    final parsed = DateTime.tryParse(raw);
    if (parsed == null) return ' \u00b7 $raw';
    return ' \u00b7 ${formatDay(parsed)}';
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: Text('Assessments · ${widget.clazz.displayLabel}')),
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
                  if (_items.isEmpty && _error == null)
                    const EmptyState(
                      icon: Icons.grade_outlined,
                      title: 'No assessments yet',
                      subtitle: 'Assessments for this class will appear here.',
                    ),
                  for (final a in _items)
                    Padding(
                      padding: const EdgeInsets.only(bottom: 10),
                      child: Card(
                        child: ListTile(
                          onTap: () => Navigator.of(context).push(
                            MaterialPageRoute<void>(
                              builder: (_) => MarksScreen(
                                controller: widget.controller,
                                clazz: widget.clazz,
                                assessment: a,
                              ),
                            ),
                          ),
                          leading: Container(
                            padding: const EdgeInsets.symmetric(
                              horizontal: 10,
                              vertical: 8,
                            ),
                            decoration: BoxDecoration(
                              color: Theme.of(context).colorScheme.secondaryContainer,
                              borderRadius: BorderRadius.circular(10),
                            ),
                            child: Text(
                              a.code,
                              style: TextStyle(
                                fontWeight: FontWeight.w700,
                                color: Theme.of(context).colorScheme.onSecondaryContainer,
                              ),
                            ),
                          ),
                          title: Text(
                            a.name,
                            style: const TextStyle(fontWeight: FontWeight.w600),
                          ),
                          subtitle: Text(
                            'Max ${a.maxMarks} marks${_scheduledLabel(a.scheduledOn)}',
                          ),
                          trailing: Icon(
                            Icons.chevron_right,
                            color: Theme.of(context).colorScheme.onSurfaceVariant,
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
