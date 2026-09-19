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
  static const _types = ['students', 'guardians', 'student_guardians', 'staff', 'enrollments'];

  String _importType = 'students';
  List<int>? _bytes;
  String? _filename;
  ImportValidateResult? _validation;
  ImportApplyResult? _applyResult;
  String? _error;
  bool _busy = false;

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
        content: TextField(controller: controller, maxLines: 12),
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

  Future<void> _validate() async {
    if (_bytes == null) {
      setState(() => _error = 'Choose a CSV file first');
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
    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        DropdownButtonFormField<String>(
          initialValue: _importType,
          decoration: const InputDecoration(labelText: 'Import type'),
          items: _types.map((t) => DropdownMenuItem(value: t, child: Text(t))).toList(),
          onChanged: _busy ? null : (v) => setState(() => _importType = v ?? _importType),
        ),
        const SizedBox(height: 12),
        OutlinedButton.icon(onPressed: _busy ? null : _loadTemplate, icon: const Icon(Icons.download), label: const Text('Copy template header')),
        OutlinedButton.icon(onPressed: _busy ? null : _pasteCsv, icon: const Icon(Icons.upload_file), label: const Text('Paste CSV')),
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
              'Applied ${_applyResult!.appliedCount}, skipped ${_applyResult!.skippedCount}',
              style: const TextStyle(fontWeight: FontWeight.bold),
            ),
          ),
        if (_error != null)
          Padding(
            padding: const EdgeInsets.only(top: 16),
            child: Text(_error!, style: const TextStyle(color: Colors.red)),
          ),
      ],
    );
  }
}
