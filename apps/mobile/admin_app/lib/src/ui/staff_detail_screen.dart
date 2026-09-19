import 'package:flutter/material.dart';

import '../app/admin_dependencies.dart';
import '../people/admin_people_api.dart';
import '../people/people_models.dart';
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
    return Scaffold(
      appBar: AppBar(
        title: const Text('Staff'),
        actions: [
          if (_staff != null) IconButton(onPressed: _edit, icon: const Icon(Icons.edit)),
        ],
      ),
      body: _loading
          ? const Center(child: CircularProgressIndicator())
          : _error != null
              ? Center(child: Text(_error!))
              : ListView(
                  padding: const EdgeInsets.all(16),
                  children: [
                    Text(_staff!.staffType, style: Theme.of(context).textTheme.headlineSmall),
                    Text('Email: ${_staff!.email ?? '—'}'),
                    Text('Employee code: ${_staff!.employeeCode ?? '—'}'),
                  ],
                ),
    );
  }
}
