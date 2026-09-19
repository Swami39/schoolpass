import 'package:flutter/material.dart';

import '../api/teacher_errors.dart';
import '../app/teacher_app_controller.dart';
import '../notifications/teacher_notification_models.dart';

class NotificationsScreen extends StatefulWidget {
  const NotificationsScreen({required this.controller, super.key});

  final TeacherAppController controller;

  @override
  State<NotificationsScreen> createState() => _NotificationsScreenState();
}

class _NotificationsScreenState extends State<NotificationsScreen> {
  bool _loading = true;
  String? _error;
  List<TeacherNotification> _items = const [];

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
      final items = await widget.controller.deps.notificationsApi.fetchNotifications();
      if (!mounted) return;
      setState(() {
        _items = items;
        _loading = false;
      });
    } on TeacherUnauthorized {
      await widget.controller.logout();
    } catch (_) {
      if (!mounted) return;
      setState(() {
        _error = 'Could not load notifications.';
        _loading = false;
      });
    }
  }

  Future<void> _markRead(TeacherNotification item) async {
    if (item.read) return;
    try {
      final updated = await widget.controller.deps.notificationsApi.markRead(item.id);
      if (!mounted) return;
      setState(() {
        _items = _items.map((n) => n.id == updated.id ? updated : n).toList();
      });
    } on TeacherUnauthorized {
      await widget.controller.logout();
    } catch (_) {
      // ignore single mark failure
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Notifications')),
      body: RefreshIndicator(
        onRefresh: _load,
        child: _loading
            ? ListView(children: const [SizedBox(height: 200), Center(child: CircularProgressIndicator())])
            : ListView(
                padding: const EdgeInsets.all(16),
                children: [
                  if (_error != null) Text(_error!, style: TextStyle(color: Theme.of(context).colorScheme.error)),
                  if (_items.isEmpty && _error == null) const Text('No notifications.'),
                  for (final item in _items)
                    ListTile(
                      title: Text(item.title),
                      subtitle: Text(item.body),
                      trailing: item.read ? null : const Icon(Icons.circle, size: 10),
                      onTap: () => _markRead(item),
                    ),
                ],
              ),
      ),
    );
  }
}
