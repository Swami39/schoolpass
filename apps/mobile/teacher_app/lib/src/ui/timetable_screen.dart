import 'package:flutter/material.dart';

import '../api/teacher_errors.dart';
import '../app/teacher_app_controller.dart';
import '../classes/teacher_class_models.dart';
import '../timetable/teacher_timetable_models.dart';
import 'format.dart';
import 'teacher_widgets.dart';

class TimetableScreen extends StatefulWidget {
  const TimetableScreen({required this.controller, required this.clazz, super.key});

  final TeacherAppController controller;
  final TeacherClassAssignment clazz;

  @override
  State<TimetableScreen> createState() => _TimetableScreenState();
}

class _TimetableScreenState extends State<TimetableScreen> {
  bool _loading = true;
  String? _error;
  List<TeacherTimetablePeriod> _periods = const [];

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
      final all = await widget.controller.deps.timetableApi.fetchTimetable();
      if (!mounted) return;
      final filtered = all.where((p) => p.sectionId == widget.clazz.sectionId).toList()
        ..sort((a, b) {
          final day = a.dayOfWeek.compareTo(b.dayOfWeek);
          if (day != 0) return day;
          return a.periodNumber.compareTo(b.periodNumber);
        });
      setState(() {
        _periods = filtered;
        _loading = false;
      });
    } on TeacherUnauthorized {
      await widget.controller.logout();
    } catch (_) {
      if (!mounted) return;
      setState(() {
        _error = 'Could not load timetable.';
        _loading = false;
      });
    }
  }

  Future<void> _editPeriod(TeacherTimetablePeriod period) async {
    final starts = TextEditingController(text: period.startsAt);
    final ends = TextEditingController(text: period.endsAt);
    final saved = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: Text('Period ${period.periodNumber} · ${period.subjectName}'),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            TextField(controller: starts, decoration: const InputDecoration(labelText: 'Starts (HH:MM)')),
            const SizedBox(height: 12),
            TextField(controller: ends, decoration: const InputDecoration(labelText: 'Ends (HH:MM)')),
          ],
        ),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx, false), child: const Text('Cancel')),
          FilledButton(onPressed: () => Navigator.pop(ctx, true), child: const Text('Save')),
        ],
      ),
    );
    if (saved != true) return;
    try {
      await widget.controller.deps.timetableApi.updatePeriod(
        periodId: period.id,
        startsAt: starts.text.trim(),
        endsAt: ends.text.trim(),
      );
      await _load();
    } on TeacherUnauthorized {
      await widget.controller.logout();
    } on TeacherNotFound {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Not authorized to edit this period.')),
      );
    } catch (_) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Update failed. Check the time format and try again.')),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    final days = <int>{for (final p in _periods) p.dayOfWeek}.toList()..sort();
    return Scaffold(
      appBar: AppBar(title: Text('Timetable · ${widget.clazz.displayLabel}')),
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
                  if (_periods.isEmpty && _error == null)
                    const EmptyState(
                      icon: Icons.schedule_outlined,
                      title: 'No periods scheduled',
                      subtitle: 'This class has no timetable periods yet.',
                    ),
                  for (final day in days) ...[
                    SectionHeader(weekdayIndexName(day)),
                    for (final p in _periods.where((p) => p.dayOfWeek == day))
                      Padding(
                        padding: const EdgeInsets.only(bottom: 8),
                        child: Card(
                          child: ListTile(
                            leading: CircleAvatar(
                              backgroundColor:
                                  Theme.of(context).colorScheme.primaryContainer,
                              foregroundColor:
                                  Theme.of(context).colorScheme.onPrimaryContainer,
                              child: Text(
                                '${p.periodNumber}',
                                style: const TextStyle(fontWeight: FontWeight.w700),
                              ),
                            ),
                            title: Text(
                              p.subjectName,
                              style: const TextStyle(fontWeight: FontWeight.w600),
                            ),
                            subtitle: Text(
                              '${formatClock(p.startsAt)} \u2013 ${formatClock(p.endsAt)}',
                            ),
                            trailing: IconButton(
                              tooltip: 'Edit period',
                              icon: const Icon(Icons.edit_outlined),
                              onPressed: () => _editPeriod(p),
                            ),
                          ),
                        ),
                      ),
                  ],
                ],
              ),
      ),
    );
  }
}
