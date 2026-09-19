import 'package:flutter/material.dart';

import '../app/parent_app_controller.dart';
import '../preferences/notification_preferences_api.dart';

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
    return Scaffold(
      appBar: AppBar(title: const Text('Notification settings')),
      body: _loading
          ? const Center(child: CircularProgressIndicator())
          : ListView(
              children: [
                if (_error != null)
                  Padding(
                    padding: const EdgeInsets.all(16),
                    child: Text(_error!, style: TextStyle(color: Theme.of(context).colorScheme.error)),
                  ),
                for (final item in _items)
                  SwitchListTile(
                    title: Text(item.notificationType.replaceAll('_', ' ')),
                    value: item.pushEnabled,
                    onChanged: (value) => _toggle(item, value),
                  ),
              ],
            ),
    );
  }
}
