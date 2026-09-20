import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import '../app/admin_dependencies.dart';
import '../imports/admin_imports_api.dart';

class ImportsHubScreen extends StatefulWidget {
  const ImportsHubScreen({required this.deps, super.key});

  final AdminDependencies deps;

  @override
  State<ImportsHubScreen> createState() => _ImportsHubScreenState();
}

class _ImportsHubScreenState extends State<ImportsHubScreen> {
  static const _types = [
    'school_roster',
    'students',
    'guardians',
    'student_guardians',
    'staff',
    'enrollments',
  ];

  static const _sampleRoster = '''
academic_year_code,academic_year_name,year_starts_on,year_ends_on,class_code,class_name,section_name,teacher_email,subject_code,subject_name,admission_no,student_first_name,student_middle_name,student_last_name,student_dob,parent_email,parent_first_name,parent_last_name,parent_phone,relationship_type
2026-27,Academic Year 2026-27,2026-04-01,2027-03-31,10,Class 10,A,demo.teacher@schoolpass.local,MATH,Mathematics,SP-1001,Asha,,Kumar,2014-06-01,parent.asha@schoolpass.local,Ravi,Kumar,+919876543210,parent
2026-27,Academic Year 2026-27,2026-04-01,2027-03-31,10,Class 10,A,demo.teacher@schoolpass.local,MATH,Mathematics,SP-1002,Neel,,Shah,2014-08-12,parent.neel@schoolpass.local,Meera,Shah,+919876543211,parent
''';

  String _importType = 'school_roster';
  List<int>? _bytes;
  String? _filename;
  ImportValidateResult? _validation;
  ImportApplyResult? _applyResult;
  String? _error;
  bool _busy = false;

  String get _typeHelp {
    switch (_importType) {
      case 'school_roster':
        return 'One row per student. Creates the year, class, section, teacher assignment, student, parent login, and the parent-child link.';
      case 'students':
        return 'Creates student records only. Use school roster if you also need parents and classes.';
      case 'guardians':
        return 'Creates parents. Email becomes their Parent app login.';
      case 'student_guardians':
        return 'Links existing students to existing parents by admission number and parent email.';
      default:
        return 'Validate the CSV, then confirm to apply.';
    }
  }

  Future<void> _loadTemplate() async {
    setState(() {
      _error = null;
      _busy = true;
    });
    try {
      final header = await widget.deps.importsApi.fetchTemplateHeader(_importType);
      await Clipboard.setData(ClipboardData(text: header));
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Template header copied')));
      }
    } catch (e) {
      setState(() => _error = e.toString());
    } finally {
      setState(() => _busy = false);
    }
  }

  Future<void> _pasteCsv() async {
    final controller = TextEditingController();
    final pasted = await showDialog<String>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Paste CSV'),
        content: SizedBox(
          width: 480,
          child: TextField(controller: controller, maxLines: 12),
        ),
        actions: [
          TextButton(onPressed: () => Navigator.pop(context), child: const Text('Cancel')),
          FilledButton(onPressed: () => Navigator.pop(context, controller.text), child: const Text('Use')),
        ],
      ),
    );
    if (pasted == null || pasted.trim().isEmpty) return;
    setState(() {
      _bytes = utf8.encode(pasted);
      _filename = 'pasted.csv';
      _validation = null;
      _applyResult = null;
      _error = null;
    });
  }

  void _useSample() {
    setState(() {
      _importType = 'school_roster';
      _bytes = utf8.encode(_sampleRoster.trimLeft());
      _filename = 'school_roster_sample.csv';
      _validation = null;
      _applyResult = null;
      _error = null;
    });
  }

  Future<void> _validate() async {
    if (_bytes == null) {
      setState(() => _error = 'Paste a CSV first');
      return;
    }
    setState(() {
      _busy = true;
      _error = null;
    });
    try {
      final result = await widget.deps.importsApi.validateCsv(
        importType: _importType,
        bytes: _bytes!,
        filename: _filename ?? 'import.csv',
      );
      setState(() => _validation = result);
    } catch (e) {
      setState(() => _error = e.toString());
    } finally {
      setState(() => _busy = false);
    }
  }

  Future<void> _apply() async {
    final validation = _validation;
    if (validation == null || _bytes == null) return;
    if (validation.errors.isNotEmpty) return;
    setState(() {
      _busy = true;
      _error = null;
    });
    try {
      final result = await widget.deps.importsApi.applyCsv(
        importType: _importType,
        bytes: _bytes!,
        filename: _filename ?? 'import.csv',
        contentDigest: validation.contentDigest,
      );
      setState(() => _applyResult = result);
    } catch (e) {
      setState(() => _error = e.toString());
    } finally {
      setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('School data import')),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          DropdownButtonFormField<String>(
            initialValue: _importType,
            decoration: const InputDecoration(labelText: 'Import type'),
            items: _types
                .map(
                  (t) => DropdownMenuItem(
                    value: t,
                    child: Text(t == 'school_roster' ? 'School roster (recommended)' : t),
                  ),
                )
                .toList(),
            onChanged: _busy
                ? null
                : (v) => setState(() {
                      _importType = v ?? _importType;
                      _validation = null;
                      _applyResult = null;
                    }),
          ),
          const SizedBox(height: 8),
          Text(_typeHelp),
          const SizedBox(height: 12),
          OutlinedButton.icon(
            onPressed: _busy ? null : _loadTemplate,
            icon: const Icon(Icons.download),
            label: const Text('Copy template header'),
          ),
          OutlinedButton.icon(
            onPressed: _busy ? null : _pasteCsv,
            icon: const Icon(Icons.upload_file),
            label: const Text('Paste CSV'),
          ),
          OutlinedButton.icon(
            onPressed: _busy ? null : _useSample,
            icon: const Icon(Icons.dataset),
            label: const Text('Load sample school roster'),
          ),
          if (_filename != null) Text('File: $_filename'),
          const SizedBox(height: 12),
          FilledButton(onPressed: _busy ? null : _validate, child: const Text('Validate')),
          if (_validation != null) ...[
            const SizedBox(height: 16),
            Text('Rows: ${_validation!.rowCount}, valid: ${_validation!.validRowCount}'),
            for (final err in _validation!.errors)
              Text('Row ${err.rowNumber}: ${err.message}', style: const TextStyle(color: Colors.red)),
            if (_validation!.errors.isEmpty)
              FilledButton(onPressed: _busy ? null : _apply, child: const Text('Confirm import')),
          ],
          if (_applyResult != null)
            Padding(
              padding: const EdgeInsets.only(top: 16),
              child: Text(
                'Imported ${_applyResult!.appliedCount} row(s), skipped ${_applyResult!.skippedCount}. '
                'Parents can sign in with their email and the school directory password.',
                style: const TextStyle(fontWeight: FontWeight.bold),
              ),
            ),
          if (_error != null)
            Padding(
              padding: const EdgeInsets.only(top: 16),
              child: Text(_error!, style: const TextStyle(color: Colors.red)),
            ),
        ],
      ),
    );
  }
}
