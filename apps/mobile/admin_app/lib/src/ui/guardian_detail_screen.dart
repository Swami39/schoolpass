import 'package:flutter/material.dart';

import '../app/admin_dependencies.dart';
import '../people/admin_people_api.dart';
import '../people/people_models.dart';
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
    return Scaffold(
      appBar: AppBar(
        title: const Text('Guardian'),
        actions: [
          if (_guardian != null) IconButton(onPressed: _edit, icon: const Icon(Icons.edit)),
        ],
      ),
      body: _loading
          ? const Center(child: CircularProgressIndicator())
          : _error != null
              ? Center(child: Text(_error!))
              : ListView(
                  padding: const EdgeInsets.all(16),
                  children: [
                    Text(_guardian!.displayName, style: Theme.of(context).textTheme.headlineSmall),
                    Text('Status: ${_guardian!.status}'),
                    Text('Phone: ${_guardian!.phoneE164 ?? '—'}'),
                    Text('Email: ${_guardian!.email ?? '—'}'),
                  ],
                ),
    );
  }
}
