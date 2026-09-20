import 'package:flutter/material.dart';

import '../app/parent_app_controller.dart';
import '../attendance/attendance_api.dart';
import '../attendance/attendance_models.dart';

class AttendanceScreen extends StatefulWidget {
  const AttendanceScreen({required this.controller, required this.studentId, super.key});

  final ParentAppController controller;
  final String studentId;

  @override
  State<AttendanceScreen> createState() => _AttendanceScreenState();
}

class _AttendanceScreenState extends State<AttendanceScreen> {
  bool _loading = true;
  String? _error;
  List<AttendanceRecordItem> _items = const [];

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
      final today = DateTime.now();
      final from = today.subtract(const Duration(days: 30));
      final items = await widget.controller.deps.attendanceApi.fetchAttendance(
        studentId: widget.studentId,
        fromDate: from.toIso8601String().split('T').first,
        toDate: today.toIso8601String().split('T').first,
        limit: 30,
      );
      if (!mounted) return;
      setState(() {
        _items = items;
        _loading = false;
      });
    } on AttendanceUnauthorized {
      if (!mounted) return;
      setState(() {
        _error = 'Could not load attendance for this child.';
        _items = [];
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

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Attendance')),
      body: RefreshIndicator(
        onRefresh: _load,
        child: _loading
            ? ListView(children: const [SizedBox(height: 200), Center(child: CircularProgressIndicator())])
            : ListView(
                padding: const EdgeInsets.all(16),
                children: [
                  if (_error != null) Text(_error!, style: TextStyle(color: Theme.of(context).colorScheme.error)),
                  if (_items.isEmpty && _error == null) const Text('No attendance records in the last 30 days.'),
                  for (final item in _items) ...[
                    Text(item.attendanceDate, style: Theme.of(context).textTheme.titleMedium),
                    ListTile(
                      title: const Text('Status'),
                      subtitle: Text(item.status),
                    ),
                    if (item.entryAt != null)
                      ListTile(
                        title: const Text('School entry'),
                        subtitle: Text(item.entryAt!.toLocal().toString()),
                      ),
                    if (item.exitAt != null)
                      ListTile(
                        title: const Text('School exit'),
                        subtitle: Text(item.exitAt!.toLocal().toString()),
                      ),
                    const Divider(),
                  ],
                ],
              ),
      ),
    );
  }
}
