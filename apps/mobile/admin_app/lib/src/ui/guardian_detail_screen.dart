import 'package:flutter/material.dart';

import '../app/admin_dependencies.dart';
import '../people/admin_people_api.dart';
import '../people/people_models.dart';
import 'admin_widgets.dart';
import 'guardian_form_screen.dart';

class GuardianDetailScreen extends StatefulWidget {
  const GuardianDetailScreen({required this.deps, required this.guardianId, super.key});

  final AdminDependencies deps;
  final String guardianId;

  @override
  State<GuardianDetailScreen> createState() => _GuardianDetailScreenState();
}

class _GuardianDetailScreenState extends State<GuardianDetailScreen> {
  bool _loading = true;
  String? _error;
  GuardianDetail? _guardian;

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
      _guardian = await widget.deps.peopleApi.fetchGuardian(widget.guardianId);
    } on AdminPeopleUnauthorized {
      _error = 'Session expired.';
    } on AdminPeopleApiFailure catch (e) {
      _error = e.message;
    } catch (_) {
      _error = 'Could not load guardian.';
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  Future<void> _edit() async {
    final changed = await Navigator.of(context).push<bool>(
      MaterialPageRoute(builder: (_) => GuardianFormScreen(deps: widget.deps, existing: _guardian)),
    );
    if (changed == true) _load();
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final guardian = _guardian;
    return Scaffold(
      appBar: AppBar(
        title: Text(guardian?.displayName ?? 'Guardian'),
        actions: [
          if (guardian != null)
            IconButton(onPressed: _edit, icon: const Icon(Icons.edit), tooltip: 'Edit'),
        ],
      ),
      body: _loading
          ? const Center(child: CircularProgressIndicator())
          : _error != null
              ? ErrorRetry(message: _error!, onRetry: _load)
              : ListView(
                  padding: const EdgeInsets.all(16),
                  children: [
                    Card(
                      child: Padding(
                        padding: const EdgeInsets.all(16),
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Row(
                              children: [
                                Expanded(
                                  child: Text(
                                    guardian!.displayName,
                                    style: theme.textTheme.headlineSmall?.copyWith(
                                      fontWeight: FontWeight.w700,
                                    ),
                                  ),
                                ),
                                StatusChip(status: guardian.status),
                              ],
                            ),
                            const SizedBox(height: 12),
                            InfoRow(label: 'Phone', value: guardian.phoneE164 ?? '—'),
                            InfoRow(label: 'Email', value: guardian.email ?? '—'),
                            InfoRow(
                              label: 'Parent app',
                              value: guardian.userId == null
                                  ? 'No login yet'
                                  : 'Login linked',
                            ),
                          ],
                        ),
                      ),
                    ),
                  ],
                ),
    );
  }
}
