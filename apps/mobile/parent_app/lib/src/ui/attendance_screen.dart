import 'package:flutter/material.dart';

import '../app/parent_app_controller.dart';
import '../attendance/attendance_api.dart';
import '../attendance/attendance_models.dart';
import 'format.dart';
import 'widgets.dart';

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
    final theme = Theme.of(context);
    return Scaffold(
      appBar: AppBar(title: const Text('Attendance')),
      body: RefreshIndicator(
        onRefresh: _load,
        child: _loading
            ? ListView(
                children: const [
                  SizedBox(height: 200),
                  Center(child: CircularProgressIndicator()),
                ],
              )
            : _items.isEmpty
                ? ListView(
                    children: [
                      if (_error != null)
                        Padding(padding: const EdgeInsets.all(16), child: ErrorBanner(message: _error!))
                      else
                        const EmptyState(
                          icon: Icons.fact_check_outlined,
                          title: 'No records yet',
                          subtitle: 'Attendance for the last 30 days will appear here.',
                        ),
                    ],
                  )
                : ListView(
                    padding: const EdgeInsets.all(16),
                    children: [
                      if (_error != null) ...[
                        ErrorBanner(message: _error!),
                        const SizedBox(height: 12),
                      ],
                      _SummaryRow(items: _items),
                      const SizedBox(height: 12),
                      Text(
                        'Daily record · last 30 days',
                        style: theme.textTheme.titleSmall?.copyWith(
                          color: theme.colorScheme.onSurfaceVariant,
                        ),
                      ),
                      const SizedBox(height: 8),
                      for (final item in _items) ...[
                        _DayCard(item: item),
                        const SizedBox(height: 8),
                      ],
                    ],
                  ),
      ),
    );
  }
}

class _SummaryRow extends StatelessWidget {
  const _SummaryRow({required this.items});

  final List<AttendanceRecordItem> items;

  @override
  Widget build(BuildContext context) {
    var present = 0;
    var absent = 0;
    for (final item in items) {
      final s = item.status.toLowerCase();
      if (s.contains('present')) {
        present++;
      } else if (s.contains('absent')) {
        absent++;
      }
    }
    return Row(
      children: [
        Expanded(child: _StatChip(label: 'Days recorded', value: '${items.length}', icon: Icons.calendar_month_outlined)),
        const SizedBox(width: 8),
        Expanded(child: _StatChip(label: 'Present', value: '$present', icon: Icons.check_circle_outline)),
        const SizedBox(width: 8),
        Expanded(child: _StatChip(label: 'Absent', value: '$absent', icon: Icons.cancel_outlined)),
      ],
    );
  }
}

class _StatChip extends StatelessWidget {
  const _StatChip({required this.label, required this.value, required this.icon});

  final String label;
  final String value;
  final IconData icon;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Card(
      child: Padding(
        padding: const EdgeInsets.symmetric(vertical: 12, horizontal: 8),
        child: Column(
          children: [
            Icon(icon, size: 20, color: theme.colorScheme.primary),
            const SizedBox(height: 4),
            Text(value, style: theme.textTheme.titleLarge?.copyWith(fontWeight: FontWeight.w800)),
            Text(label, style: theme.textTheme.bodySmall),
          ],
        ),
      ),
    );
  }
}

class _DayCard extends StatelessWidget {
  const _DayCard({required this.item});

  final AttendanceRecordItem item;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final date = DateTime.tryParse(item.attendanceDate);
    final entry = item.entryAt?.toLocal();
    final exit = item.exitAt?.toLocal();
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Expanded(
                  child: Text(
                    date != null ? formatDayYear(date) : item.attendanceDate,
                    style: theme.textTheme.titleMedium?.copyWith(fontWeight: FontWeight.w600),
                  ),
                ),
                _StatusChip(status: item.status),
              ],
            ),
            if (entry != null || exit != null) ...[
              const SizedBox(height: 12),
              Row(
                children: [
                  Icon(Icons.login_outlined, size: 18, color: theme.colorScheme.onSurfaceVariant),
                  const SizedBox(width: 6),
                  Text(entry != null ? 'In ${formatTime(entry)}' : 'In —',
                      style: theme.textTheme.bodyMedium),
                  const SizedBox(width: 16),
                  Icon(Icons.logout_outlined, size: 18, color: theme.colorScheme.onSurfaceVariant),
                  const SizedBox(width: 6),
                  Text(exit != null ? 'Out ${formatTime(exit)}' : 'Out —',
                      style: theme.textTheme.bodyMedium),
                ],
              ),
            ],
          ],
        ),
      ),
    );
  }
}

class _StatusChip extends StatelessWidget {
  const _StatusChip({required this.status});

  final String status;

  @override
  Widget build(BuildContext context) {
    final s = status.toLowerCase();
    late final Color bg;
    late final Color fg;
    late final IconData icon;
    if (s.contains('present')) {
      bg = const Color(0xFFE6F4EA);
      fg = const Color(0xFF137333);
      icon = Icons.check_circle;
    } else if (s.contains('absent')) {
      bg = const Color(0xFFFCE8E6);
      fg = const Color(0xFFA50E0E);
      icon = Icons.cancel;
    } else if (s.contains('late')) {
      bg = const Color(0xFFFEF7E0);
      fg = const Color(0xFF7A4A00);
      icon = Icons.schedule;
    } else {
      bg = const Color(0xFFE8EAED);
      fg = const Color(0xFF3C4043);
      icon = Icons.info;
    }
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
      decoration: BoxDecoration(color: bg, borderRadius: BorderRadius.circular(20)),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(icon, size: 14, color: fg),
          const SizedBox(width: 4),
          Text(
            prettifyLabel(status),
            style: TextStyle(color: fg, fontWeight: FontWeight.w600, fontSize: 12),
          ),
        ],
      ),
    );
  }
}
