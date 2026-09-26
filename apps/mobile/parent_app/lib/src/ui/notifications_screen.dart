import 'package:flutter/material.dart';
import 'package:schoolpass_design/schoolpass_design.dart';

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
      appBar: AppBar(title: const DesignAppBarTitle('Notifications')),
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
                    padding: const EdgeInsets.all(16),
                    itemCount: _items.length,
                    separatorBuilder: (_, __) => const SizedBox(height: 10),
                    itemBuilder: (context, index) {
                      final item = _items[index];
                      return _NotificationCard(item: item, onTap: () => _markRead(item));
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

/// Maps a free-form backend notification type onto the design system's
/// meaning-carrying status palette (mirrors [_iconForType]'s heuristics).
StatusKind _kindForType(String type) {
  final t = type.toLowerCase();
  if (t.contains('bus') || t.contains('trip') || t.contains('drop') || t.contains('board')) {
    return StatusKind.bus;
  }
  if (t.contains('absent')) return StatusKind.absent;
  if (t.contains('late')) return StatusKind.late;
  if (t.contains('attend') ||
      t.contains('present') ||
      t.contains('entry') ||
      t.contains('exit') ||
      t.contains('gate')) {
    return StatusKind.present;
  }
  return StatusKind.neutral;
}

class _NotificationCard extends StatelessWidget {
  const _NotificationCard({required this.item, required this.onTap});

  final ParentNotification item;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final status = context.status;
    final kind = _kindForType(item.notificationType);
    final color = status.of(kind);
    final iconColor = item.read ? color.withValues(alpha: 0.55) : color;
    return Panel(
      onTap: onTap,
      padding: const EdgeInsets.all(14),
      radius: BorderRadius.circular(18),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Container(
            width: 44,
            height: 44,
            decoration: BoxDecoration(
              color: status.softOf(kind),
              borderRadius: BorderRadius.circular(14),
            ),
            child: Icon(_iconForType(item.notificationType), color: iconColor),
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Expanded(
                      child: Text(
                        item.title,
                        style: TextStyle(
                          fontWeight: item.read ? FontWeight.w500 : FontWeight.w700,
                          fontSize: 14,
                        ),
                      ),
                    ),
                    if (!item.read) ...[
                      const SizedBox(width: 8),
                      Container(
                        width: 10,
                        height: 10,
                        margin: const EdgeInsets.only(top: 4),
                        decoration: const BoxDecoration(
                          color: DesignColors.brand,
                          shape: BoxShape.circle,
                        ),
                      ),
                    ],
                  ],
                ),
                const SizedBox(height: 3),
                Text(
                  item.body,
                  maxLines: 2,
                  overflow: TextOverflow.ellipsis,
                  style: const TextStyle(fontSize: 13, color: DesignColors.ink2),
                ),
                const SizedBox(height: 8),
                Row(
                  children: [
                    StatusPill(kind: kind, label: prettifyLabel(item.notificationType)),
                    const Spacer(),
                    Text(
                      relativeTime(item.createdAt.toLocal()),
                      style: DesignTypography.mono(size: 11.5, color: DesignColors.ink3),
                    ),
                  ],
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}
