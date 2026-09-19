import 'package:flutter/material.dart';

import '../api/teacher_errors.dart';
import '../app/teacher_app_controller.dart';
import '../classes/teacher_class_models.dart';
import '../timetable/teacher_timetable_models.dart';

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
      setState(() {
        _periods = all.where((p) => p.sectionId == widget.clazz.sectionId).toList();
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
        title: const Text('Edit period'),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            TextField(controller: starts, decoration: const InputDecoration(labelText: 'Starts (HH:MM:SS)')),
            TextField(controller: ends, decoration: const InputDecoration(labelText: 'Ends (HH:MM:SS)')),
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
        const SnackBar(content: Text('Update failed.')),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    const days = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];
    return Scaffold(
      appBar: AppBar(title: Text('Timetable · ${widget.clazz.displayLabel}')),
      body: RefreshIndicator(
        onRefresh: _load,
        child: _loading
            ? ListView(children: const [SizedBox(height: 200), Center(child: CircularProgressIndicator())])
            : ListView(
                padding: const EdgeInsets.all(16),
                children: [
                  if (_error != null) Text(_error!, style: TextStyle(color: Theme.of(context).colorScheme.error)),
                  if (_periods.isEmpty && _error == null) const Text('No periods for this class.'),
                  for (final p in _periods)
                    ListTile(
                      title: Text('${days[p.dayOfWeek]} · Period ${p.periodNumber} · ${p.subjectName}'),
                      subtitle: Text('${p.startsAt} – ${p.endsAt}'),
                      trailing: IconButton(
                        icon: const Icon(Icons.edit_outlined),
                        onPressed: () => _editPeriod(p),
                      ),
                    ),
                ],
              ),
      ),
    );
  }
}
