import 'package:flutter/material.dart';

import '../api/teacher_errors.dart';
import '../app/teacher_app_controller.dart';
import '../notifications/teacher_notification_models.dart';
import 'format.dart';
import 'teacher_widgets.dart';

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

  int get _unreadCount => _items.where((n) => !n.read).length;

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

  IconData _iconFor(String type) {
    final t = type.toLowerCase();
    if (t.contains('attendance')) return Icons.fact_check_outlined;
    if (t.contains('fee') || t.contains('payment')) return Icons.payments_outlined;
    if (t.contains('bus') || t.contains('trip')) return Icons.directions_bus_outlined;
    if (t.contains('urgent') || t.contains('alert')) return Icons.warning_amber_outlined;
    if (t.contains('result') || t.contains('mark')) return Icons.grade_outlined;
    if (t.contains('message')) return Icons.message_outlined;
    return Icons.notifications_outlined;
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final scheme = theme.colorScheme;
    return Scaffold(
      appBar: AppBar(title: const Text('Notifications')),
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
                      icon: Icons.notifications_none_outlined,
                      title: 'All caught up',
                      subtitle: 'You have no notifications right now.',
                    ),
                  if (_items.isNotEmpty) ...[
                    Text(
                      _unreadCount == 0
                          ? 'Everything read'
                          : '$_unreadCount unread',
                      style: theme.textTheme.titleSmall?.copyWith(
                        color: scheme.onSurfaceVariant,
                        fontWeight: FontWeight.w600,
                      ),
                    ),
                    const SizedBox(height: 8),
                    for (final item in _items)
                      Padding(
                        padding: const EdgeInsets.only(bottom: 8),
                        child: Card(
                          color: item.read ? null : scheme.primaryContainer,
                          child: ListTile(
                            onTap: () => _markRead(item),
                            leading: Container(
                              width: 42,
                              height: 42,
                              decoration: BoxDecoration(
                                color: item.read
                                    ? scheme.surfaceContainerHighest
                                    : scheme.primary.withValues(alpha: 0.15),
                                borderRadius: BorderRadius.circular(12),
                              ),
                              child: Icon(
                                _iconFor(item.notificationType),
                                color: item.read
                                    ? scheme.onSurfaceVariant
                                    : scheme.primary,
                              ),
                            ),
                            title: Text(
                              item.title,
                              style: TextStyle(
                                fontWeight:
                                    item.read ? FontWeight.normal : FontWeight.w700,
                              ),
                            ),
                            subtitle: Column(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                const SizedBox(height: 4),
                                Text(item.body),
                                const SizedBox(height: 4),
                                Text(
                                  relativeTime(item.createdAt),
                                  style: theme.textTheme.bodySmall?.copyWith(
                                    color: scheme.onSurfaceVariant,
                                  ),
                                ),
                              ],
                            ),
                            trailing: item.read
                                ? null
                                : Icon(
                                    Icons.circle,
                                    size: 10,
                                    color: scheme.primary,
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
