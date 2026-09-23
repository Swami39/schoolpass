import 'package:flutter/material.dart';

import '../app/parent_app_controller.dart';
import '../preferences/notification_preferences_api.dart';
import 'format.dart';
import 'widgets.dart';

class NotificationPreferencesScreen extends StatefulWidget {
  const NotificationPreferencesScreen({required this.controller, super.key});

  final ParentAppController controller;

  @override
  State<NotificationPreferencesScreen> createState() => _NotificationPreferencesScreenState();
}

class _NotificationPreferencesScreenState extends State<NotificationPreferencesScreen> {
  bool _loading = true;
  String? _error;
  List<NotificationPreferenceItem> _items = const [];

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
      final items = await widget.controller.deps.preferencesApi.fetchPreferences();
      if (!mounted) return;
      setState(() {
        _items = items;
        _loading = false;
      });
    } catch (_) {
      if (!mounted) return;
      setState(() {
        _error = 'Could not load preferences.';
        _loading = false;
      });
    }
  }

  Future<void> _toggle(NotificationPreferenceItem item, bool enabled) async {
    final previous = List<NotificationPreferenceItem>.from(_items);
    final optimistic = _items
        .map((p) => p.notificationType == item.notificationType
            ? NotificationPreferenceItem(notificationType: p.notificationType, pushEnabled: enabled)
            : p)
        .toList(growable: false);
    setState(() => _items = optimistic);
    try {
      final saved = await widget.controller.deps.preferencesApi.savePreferences(optimistic);
      if (!mounted) return;
      setState(() => _items = saved);
    } catch (_) {
      if (!mounted) return;
      setState(() {
        _items = previous;
        _error = 'Could not save preference.';
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Scaffold(
      appBar: AppBar(title: const Text('Notification settings')),
      body: _loading
          ? const Center(child: CircularProgressIndicator())
          : ListView(
              padding: const EdgeInsets.all(16),
              children: [
                if (_error != null) ...[
                  ErrorBanner(message: _error!),
                  const SizedBox(height: 12),
                ],
                Text(
                  'Choose which push alerts you receive on this phone.',
                  style: theme.textTheme.bodyMedium?.copyWith(
                    color: theme.colorScheme.onSurfaceVariant,
                  ),
                ),
                const SizedBox(height: 12),
                if (_items.isEmpty && _error == null)
                  const EmptyState(
                    icon: Icons.tune_outlined,
                    title: 'No alert types yet',
                    subtitle: 'Your school has not configured any alerts.',
                  )
                else
                  Card(
                    child: Column(
                      children: [
                        for (var i = 0; i < _items.length; i++) ...[
                          SwitchListTile(
                            title: Text(
                              prettifyLabel(_items[i].notificationType),
                              style: const TextStyle(fontWeight: FontWeight.w500),
                            ),
                            subtitle: Text(_describe(_items[i].notificationType)),
                            value: _items[i].pushEnabled,
                            onChanged: (value) => _toggle(_items[i], value),
                          ),
                          if (i != _items.length - 1) const Divider(height: 1, indent: 16),
                        ],
                      ],
                    ),
                  ),
              ],
            ),
    );
  }
}

String _describe(String type) {
  final t = type.toLowerCase();
  if (t.contains('board')) return 'When your child boards the school bus';
  if (t.contains('drop')) return 'When your child is dropped off';
  if (t.contains('attend')) return 'Daily school attendance updates';
  if (t.contains('fee') || t.contains('payment')) return 'Fee reminders and payment updates';
  if (t.contains('emergency')) return 'Urgent alerts from the school';
  return 'Alerts of this type from the school';
}
