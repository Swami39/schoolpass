import 'package:flutter/material.dart';

import '../app/admin_dependencies.dart';
import '../people/admin_people_api.dart';
import '../people/people_models.dart';

class GuardianFormScreen extends StatefulWidget {
  const GuardianFormScreen({required this.deps, this.existing, super.key});

  final AdminDependencies deps;
  final GuardianDetail? existing;

  @override
  State<GuardianFormScreen> createState() => _GuardianFormScreenState();
}

class _GuardianFormScreenState extends State<GuardianFormScreen> {
  final _firstCtrl = TextEditingController();
  final _lastCtrl = TextEditingController();
  final _phoneCtrl = TextEditingController();
  final _emailCtrl = TextEditingController();
  bool _submitting = false;
  String? _error;

  @override
  void initState() {
    super.initState();
    final e = widget.existing;
    if (e != null) {
      _firstCtrl.text = e.firstName;
      _lastCtrl.text = e.lastName;
      _phoneCtrl.text = e.phoneE164 ?? '';
      _emailCtrl.text = e.email ?? '';
    }
  }

  @override
  void dispose() {
    _firstCtrl.dispose();
    _lastCtrl.dispose();
    _phoneCtrl.dispose();
    _emailCtrl.dispose();
    super.dispose();
  }

  Future<void> _submit() async {
    setState(() {
      _submitting = true;
      _error = null;
    });
    final body = <String, dynamic>{
      'first_name': _firstCtrl.text.trim(),
      'last_name': _lastCtrl.text.trim(),
      'phone_e164': _phoneCtrl.text.trim().isEmpty ? null : _phoneCtrl.text.trim(),
      'email': _emailCtrl.text.trim().isEmpty ? null : _emailCtrl.text.trim(),
    };
    try {
      if (widget.existing != null) {
        await widget.deps.peopleApi.updateGuardian(widget.existing!.id, body);
      } else {
        await widget.deps.peopleApi.createGuardian(body);
      }
      if (mounted) Navigator.of(context).pop(true);
    } on AdminPeopleUnauthorized {
      setState(() => _error = 'Session expired.');
    } on AdminPeopleApiFailure catch (e) {
      setState(() => _error = e.message);
    } catch (_) {
      setState(() => _error = 'Could not save guardian.');
    } finally {
      if (mounted) setState(() => _submitting = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: Text(widget.existing == null ? 'New guardian' : 'Edit guardian')),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          TextField(controller: _firstCtrl, decoration: const InputDecoration(labelText: 'First name')),
          TextField(controller: _lastCtrl, decoration: const InputDecoration(labelText: 'Last name')),
          TextField(controller: _phoneCtrl, decoration: const InputDecoration(labelText: 'Phone (E.164)')),
          TextField(controller: _emailCtrl, decoration: const InputDecoration(labelText: 'Email (Parent app login)')),
          const SizedBox(height: 8),
          const Text(
            'Saving with an email creates a parent login. First-time password is the school directory password.',
          ),
          if (_error != null) Text(_error!, style: TextStyle(color: Theme.of(context).colorScheme.error)),
          const SizedBox(height: 16),
          FilledButton(
            onPressed: _submitting ? null : _submit,
            child: _submitting ? const CircularProgressIndicator() : const Text('Save'),
          ),
        ],
      ),
    );
  }
}
