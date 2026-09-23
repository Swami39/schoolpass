import 'package:flutter/material.dart';

import '../app/admin_dependencies.dart';
import '../people/admin_people_api.dart';
import '../people/people_models.dart';
import 'admin_widgets.dart';
import 'format.dart';
import 'staff_form_screen.dart';

class StaffDetailScreen extends StatefulWidget {
  const StaffDetailScreen({required this.deps, required this.staffId, super.key});

  final AdminDependencies deps;
  final String staffId;

  @override
  State<StaffDetailScreen> createState() => _StaffDetailScreenState();
}

class _StaffDetailScreenState extends State<StaffDetailScreen> {
  bool _loading = true;
  String? _error;
  StaffDetail? _staff;

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
      _staff = await widget.deps.peopleApi.fetchStaffMember(widget.staffId);
    } on AdminPeopleUnauthorized {
      _error = 'Session expired.';
    } on AdminPeopleApiFailure catch (e) {
      _error = e.message;
    } catch (_) {
      _error = 'Could not load staff.';
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  Future<void> _edit() async {
    final changed = await Navigator.of(context).push<bool>(
      MaterialPageRoute(builder: (_) => StaffFormScreen(deps: widget.deps, existing: _staff)),
    );
    if (changed == true) _load();
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final staff = _staff;
    return Scaffold(
      appBar: AppBar(
        title: Text(staff == null ? 'Staff' : prettifyLabel(staff.staffType)),
        actions: [
          if (staff != null)
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
                                    prettifyLabel(staff!.staffType),
                                    style: theme.textTheme.headlineSmall?.copyWith(
                                      fontWeight: FontWeight.w700,
                                    ),
                                  ),
                                ),
                                const Icon(Icons.badge_outlined, size: 32),
                              ],
                            ),
                            const SizedBox(height: 12),
                            InfoRow(label: 'Email', value: staff.email ?? '—'),
                            InfoRow(label: 'Employee code', value: staff.employeeCode ?? '—'),
                          ],
                        ),
                      ),
                    ),
                  ],
                ),
    );
  }
}
