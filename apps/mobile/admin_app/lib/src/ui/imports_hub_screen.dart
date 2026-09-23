import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import '../app/admin_dependencies.dart';
import '../imports/admin_imports_api.dart';
import 'admin_widgets.dart';
import 'format.dart';

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
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Template header copied to clipboard')),
        );
      }
    } catch (_) {
      setState(() => _error = 'Could not fetch the template. Check your connection and try again.');
    } finally {
      if (mounted) setState(() => _busy = false);
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
      setState(() => _error = 'Paste a CSV first, or load the sample.');
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
    } catch (_) {
      setState(() => _error = 'Could not validate the CSV. Check your connection and try again.');
    } finally {
      if (mounted) setState(() => _busy = false);
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
    } catch (_) {
      setState(() => _error = 'Could not apply the import. Check your connection and try again.');
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Scaffold(
      appBar: AppBar(title: const Text('School data import')),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          const SectionHeader(title: '1 · What are you importing?'),
          const SizedBox(height: 8),
          DropdownButtonFormField<String>(
            initialValue: _importType,
            decoration: const InputDecoration(labelText: 'Import type'),
            items: _types
                .map(
                  (t) => DropdownMenuItem(
                    value: t,
                    child: Text(
                      t == 'school_roster'
                          ? 'School roster (recommended)'
                          : prettifyLabel(t),
                    ),
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
          Text(
            _typeHelp,
            style: theme.textTheme.bodyMedium?.copyWith(
              color: theme.colorScheme.onSurfaceVariant,
            ),
          ),
          const SizedBox(height: 16),
          const SectionHeader(title: '2 · Get your CSV ready'),
          const SizedBox(height: 8),
          Wrap(
            spacing: 8,
            runSpacing: 8,
            children: [
              OutlinedButton.icon(
                onPressed: _busy ? null : _loadTemplate,
                icon: const Icon(Icons.content_copy_outlined),
                label: const Text('Copy template header'),
              ),
              OutlinedButton.icon(
                onPressed: _busy ? null : _pasteCsv,
                icon: const Icon(Icons.paste_outlined),
                label: const Text('Paste CSV'),
              ),
              OutlinedButton.icon(
                onPressed: _busy ? null : _useSample,
                icon: const Icon(Icons.dataset_outlined),
                label: const Text('Try the sample'),
              ),
            ],
          ),
          if (_filename != null) ...[
            const SizedBox(height: 8),
            Row(
              children: [
                Icon(Icons.attach_file, size: 16, color: theme.colorScheme.onSurfaceVariant),
                const SizedBox(width: 4),
                Expanded(child: Text(_filename!)),
              ],
            ),
          ],
          const SizedBox(height: 16),
          const SectionHeader(title: '3 · Validate'),
          const SizedBox(height: 8),
          FilledButton.icon(
            onPressed: _busy ? null : _validate,
            icon: _busy
                ? const SizedBox(
                    height: 18,
                    width: 18,
                    child: CircularProgressIndicator(strokeWidth: 2),
                  )
                : const Icon(Icons.fact_check_outlined),
            label: const Text('Validate CSV'),
          ),
          if (_validation != null) ...[
            const SizedBox(height: 16),
            const SectionHeader(title: '4 · Review & apply'),
            const SizedBox(height: 8),
            Card(
              child: Padding(
                padding: const EdgeInsets.all(16),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      children: [
                        Expanded(
                          child: _countStat(
                            theme,
                            '${_validation!.rowCount}',
                            'rows',
                          ),
                        ),
                        Expanded(
                          child: _countStat(
                            theme,
                            '${_validation!.validRowCount}',
                            'valid',
                          ),
                        ),
                        Expanded(
                          child: _countStat(
                            theme,
                            '${_validation!.errors.length}',
                            'errors',
                          ),
                        ),
                      ],
                    ),
                    if (_validation!.errors.isNotEmpty) ...[
                      const SizedBox(height: 12),
                      for (final err in _validation!.errors)
                        Padding(
                          padding: const EdgeInsets.only(bottom: 6),
                          child: Row(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Icon(Icons.error_outline, size: 16, color: theme.colorScheme.error),
                              const SizedBox(width: 8),
                              Expanded(
                                child: Text(
                                  'Row ${err.rowNumber}: ${err.message}',
                                  style: theme.textTheme.bodyMedium,
                                ),
                              ),
                            ],
                          ),
                        ),
                    ],
                  ],
                ),
              ),
            ),
            const SizedBox(height: 12),
            if (_validation!.errors.isEmpty)
              FilledButton.icon(
                onPressed: _busy ? null : _apply,
                icon: const Icon(Icons.check_circle_outline),
                label: const Text('Confirm import'),
              )
            else
              Text(
                'Fix the errors above and validate again before importing.',
                style: theme.textTheme.bodyMedium?.copyWith(
                  color: theme.colorScheme.onSurfaceVariant,
                ),
              ),
          ],
          if (_applyResult != null) ...[
            const SizedBox(height: 16),
            SuccessBanner(
              message:
                  'Imported ${_applyResult!.appliedCount} row(s), skipped ${_applyResult!.skippedCount}. '
                  'Parents can sign in with their email and the school directory password.',
            ),
          ],
          if (_error != null) ...[
            const SizedBox(height: 16),
            ErrorBanner(message: _error!),
          ],
        ],
      ),
    );
  }

  Widget _countStat(ThemeData theme, String value, String label) {
    return Column(
      children: [
        Text(
          value,
          style: theme.textTheme.headlineSmall?.copyWith(fontWeight: FontWeight.w800),
        ),
        Text(
          label,
          style: theme.textTheme.bodySmall?.copyWith(
            color: theme.colorScheme.onSurfaceVariant,
          ),
        ),
      ],
    );
  }
}
