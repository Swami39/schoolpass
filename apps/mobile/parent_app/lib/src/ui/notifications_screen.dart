import 'package:flutter/material.dart';

import '../app/parent_app_controller.dart';
import '../notifications/notification_models.dart';

class NotificationsScreen extends StatefulWidget {
  const NotificationsScreen({required this.controller, super.key});

  final ParentAppController controller;

  @override
  State<NotificationsScreen> createState() => _NotificationsScreenState();
}

class _NotificationsScreenState extends State<NotificationsScreen> {
  bool _loading = true;
  String? _error;
  List<ParentNotification> _items = const [];

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
    } catch (_) {
      if (!mounted) return;
      setState(() {
        _error = 'Could not load notifications.';
        _loading = false;
      });
    }
  }

  Future<void> _markRead(ParentNotification item) async {
    if (item.read) return;
    final updated = await widget.controller.deps.notificationsApi.markRead(item.id);
    setState(() {
      _items = _items.map((n) => n.id == updated.id ? updated : n).toList(growable: false);
    });
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
                children: [
                  if (_error != null)
                    Padding(
                      padding: const EdgeInsets.all(16),
                      child: Text(_error!, style: TextStyle(color: Theme.of(context).colorScheme.error)),
                    ),
                  if (_items.isEmpty && _error == null)
                    const Padding(padding: EdgeInsets.all(16), child: Text('No notifications yet.')),
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
