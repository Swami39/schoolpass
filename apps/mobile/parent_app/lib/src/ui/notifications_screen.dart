import 'package:flutter/material.dart';

import '../app/parent_app_controller.dart';
import '../notifications/notification_models.dart';
import 'format.dart';
import 'widgets.dart';

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
    try {
      final updated = await widget.controller.deps.notificationsApi.markRead(item.id);
      if (!mounted) return;
      setState(() {
        _items = _items.map((n) => n.id == updated.id ? updated : n).toList(growable: false);
      });
    } catch (_) {
      // Best-effort; the list still shows the notification.
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Notifications')),
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
                          icon: Icons.notifications_none_outlined,
                          title: 'You\'re all caught up',
                          subtitle: 'School alerts will appear here.',
                        ),
                    ],
                  )
                : ListView.separated(
                    padding: const EdgeInsets.symmetric(vertical: 8),
                    itemCount: _items.length,
                    separatorBuilder: (_, __) => const Divider(height: 1, indent: 72),
                    itemBuilder: (context, index) {
                      final item = _items[index];
                      return _NotificationTile(item: item, onTap: () => _markRead(item));
                    },
                  ),
      ),
    );
  }
}

IconData _iconForType(String type) {
  final t = type.toLowerCase();
  if (t.contains('bus') || t.contains('trip') || t.contains('drop')) {
    return Icons.directions_bus_outlined;
  }
  if (t.contains('attend')) return Icons.fact_check_outlined;
  if (t.contains('fee') || t.contains('payment')) return Icons.payments_outlined;
  return Icons.notifications_outlined;
}

class _NotificationTile extends StatelessWidget {
  const _NotificationTile({required this.item, required this.onTap});

  final ParentNotification item;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final scheme = theme.colorScheme;
    return ListTile(
      contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 6),
      leading: Container(
        width: 44,
        height: 44,
        decoration: BoxDecoration(
          color: item.read ? scheme.surfaceContainerHighest : scheme.primaryContainer,
          borderRadius: BorderRadius.circular(12),
        ),
        child: Icon(
          _iconForType(item.notificationType),
          color: item.read ? scheme.onSurfaceVariant : scheme.onPrimaryContainer,
        ),
      ),
      title: Text(
        item.title,
        style: TextStyle(fontWeight: item.read ? FontWeight.w400 : FontWeight.w700),
      ),
      subtitle: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const SizedBox(height: 2),
          Text(item.body, maxLines: 2, overflow: TextOverflow.ellipsis),
          const SizedBox(height: 4),
          Text(
            relativeTime(item.createdAt.toLocal()),
            style: theme.textTheme.bodySmall?.copyWith(color: scheme.onSurfaceVariant),
          ),
        ],
      ),
      trailing: item.read
          ? null
          : Container(
              width: 10,
              height: 10,
              decoration: BoxDecoration(color: scheme.primary, shape: BoxShape.circle),
            ),
      onTap: onTap,
    );
  }
}
