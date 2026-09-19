import 'package:flutter/material.dart';

import '../app/admin_dependencies.dart';
import '../people/admin_people_api.dart';
import '../people/people_models.dart';

class StudentFormScreen extends StatefulWidget {
  const StudentFormScreen({required this.deps, this.existing, super.key});

  final AdminDependencies deps;
  final StudentDetail? existing;

  bool get isEdit => existing != null;

  @override
  State<StudentFormScreen> createState() => _StudentFormScreenState();
}

class _StudentFormScreenState extends State<StudentFormScreen> {
  final _admissionCtrl = TextEditingController();
  final _firstCtrl = TextEditingController();
  final _middleCtrl = TextEditingController();
  final _lastCtrl = TextEditingController();
  bool _submitting = false;
  String? _error;

  @override
  void initState() {
    super.initState();
    final e = widget.existing;
    if (e != null) {
      _admissionCtrl.text = e.admissionNo;
      _firstCtrl.text = e.firstName;
      _middleCtrl.text = e.middleName ?? '';
      _lastCtrl.text = e.lastName;
    }
  }

  @override
  void dispose() {
    _admissionCtrl.dispose();
    _firstCtrl.dispose();
    _middleCtrl.dispose();
    _lastCtrl.dispose();
    super.dispose();
  }

  Future<void> _submit() async {
    if (_firstCtrl.text.trim().isEmpty || _lastCtrl.text.trim().isEmpty) {
      setState(() => _error = 'First and last name are required.');
      return;
    }
    setState(() {
      _submitting = true;
      _error = null;
    });
    try {
      if (widget.isEdit) {
        await widget.deps.peopleApi.updateStudent(widget.existing!.id, {
          'first_name': _firstCtrl.text.trim(),
          'middle_name': _middleCtrl.text.trim().isEmpty ? null : _middleCtrl.text.trim(),
          'last_name': _lastCtrl.text.trim(),
        });
      } else {
        if (_admissionCtrl.text.trim().isEmpty) {
          setState(() {
            _error = 'Admission number is required.';
            _submitting = false;
          });
          return;
        }
        await widget.deps.peopleApi.createStudent({
          'admission_no': _admissionCtrl.text.trim(),
          'first_name': _firstCtrl.text.trim(),
          'middle_name': _middleCtrl.text.trim().isEmpty ? null : _middleCtrl.text.trim(),
          'last_name': _lastCtrl.text.trim(),
        });
      }
      if (mounted) Navigator.of(context).pop(true);
    } on AdminPeopleUnauthorized {
      setState(() => _error = 'Session expired.');
    } on AdminPeopleApiFailure catch (e) {
      setState(() => _error = e.message);
    } catch (_) {
      setState(() => _error = 'Could not save student.');
    } finally {
      if (mounted) setState(() => _submitting = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: Text(widget.isEdit ? 'Edit student' : 'New student')),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          if (!widget.isEdit)
            TextField(
              controller: _admissionCtrl,
              decoration: const InputDecoration(labelText: 'Admission number'),
              textInputAction: TextInputAction.next,
            ),
          TextField(controller: _firstCtrl, decoration: const InputDecoration(labelText: 'First name')),
          TextField(controller: _middleCtrl, decoration: const InputDecoration(labelText: 'Middle name (optional)')),
          TextField(controller: _lastCtrl, decoration: const InputDecoration(labelText: 'Last name')),
          if (_error != null) ...[
            const SizedBox(height: 12),
            Text(_error!, style: TextStyle(color: Theme.of(context).colorScheme.error)),
          ],
          const SizedBox(height: 24),
          FilledButton(
            onPressed: _submitting ? null : _submit,
            child: _submitting
                ? const SizedBox(height: 20, width: 20, child: CircularProgressIndicator(strokeWidth: 2))
                : Text(widget.isEdit ? 'Save changes' : 'Create student'),
          ),
        ],
      ),
    );
  }
}
