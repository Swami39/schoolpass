import 'package:flutter/material.dart';

import '../app/admin_dependencies.dart';
import '../people/admin_people_api.dart';
import '../people/people_models.dart';

class StaffFormScreen extends StatefulWidget {
  const StaffFormScreen({required this.deps, this.existing, super.key});

  final AdminDependencies deps;
  final StaffDetail? existing;

  @override
  State<StaffFormScreen> createState() => _StaffFormScreenState();
}

class _StaffFormScreenState extends State<StaffFormScreen> {
  final _userIdCtrl = TextEditingController();
  final _codeCtrl = TextEditingController();
  String _staffType = 'teacher';
  bool _submitting = false;
  String? _error;

  static const _types = ['teacher', 'attendant', 'bus_attendant', 'office', 'finance'];

  @override
  void initState() {
    super.initState();
    final e = widget.existing;
    if (e != null) {
      _staffType = e.staffType;
      _codeCtrl.text = e.employeeCode ?? '';
    }
  }

  @override
  void dispose() {
    _userIdCtrl.dispose();
    _codeCtrl.dispose();
    super.dispose();
  }

  Future<void> _submit() async {
    setState(() {
      _submitting = true;
      _error = null;
    });
    try {
      if (widget.existing != null) {
        await widget.deps.peopleApi.updateStaff(widget.existing!.id, {
          'staff_type': _staffType,
          'employee_code': _codeCtrl.text.trim().isEmpty ? null : _codeCtrl.text.trim(),
        });
      } else {
        if (_userIdCtrl.text.trim().isEmpty) {
          setState(() {
            _error = 'User ID is required (existing platform user).';
            _submitting = false;
          });
          return;
        }
        await widget.deps.peopleApi.createStaff({
          'user_id': _userIdCtrl.text.trim(),
          'staff_type': _staffType,
          'employee_code': _codeCtrl.text.trim().isEmpty ? null : _codeCtrl.text.trim(),
        });
      }
      if (mounted) Navigator.of(context).pop(true);
    } on AdminPeopleUnauthorized {
      setState(() => _error = 'Session expired.');
    } on AdminPeopleApiFailure catch (e) {
      setState(() => _error = e.message);
    } catch (_) {
      setState(() => _error = 'Could not save staff.');
    } finally {
      if (mounted) setState(() => _submitting = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: Text(widget.existing == null ? 'New staff' : 'Edit staff')),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          if (widget.existing == null)
            TextField(
              controller: _userIdCtrl,
              decoration: const InputDecoration(
                labelText: 'User ID',
                helperText: 'UUID of an existing user account for this school',
              ),
            ),
          DropdownButtonFormField<String>(
            initialValue: _staffType,
            items: _types.map((t) => DropdownMenuItem(value: t, child: Text(t))).toList(),
            onChanged: _submitting ? null : (v) => setState(() => _staffType = v ?? _staffType),
            decoration: const InputDecoration(labelText: 'Staff type'),
          ),
          TextField(controller: _codeCtrl, decoration: const InputDecoration(labelText: 'Employee code')),
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
