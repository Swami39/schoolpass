import 'package:flutter/material.dart';

import '../app/admin_dependencies.dart';
import '../people/admin_people_api.dart';
import '../people/people_models.dart';
import 'admin_widgets.dart';

/// Attach a parent/guardian to a student: pick an existing one or create
/// a new parent (which also creates their Parent app login).
class LinkGuardianScreen extends StatefulWidget {
  const LinkGuardianScreen({
    required this.deps,
    required this.studentId,
    required this.studentName,
    super.key,
  });

  final AdminDependencies deps;
  final String studentId;
  final String studentName;

  @override
  State<LinkGuardianScreen> createState() => _LinkGuardianScreenState();
}

const _relationshipOptions = ['parent', 'mother', 'father', 'guardian', 'other'];

class _LinkGuardianScreenState extends State<LinkGuardianScreen> {
  bool _createNew = true;
  bool _loading = true;
  bool _submitting = false;
  String? _error;

  List<GuardianDetail> _guardians = const [];
  GuardianDetail? _selectedGuardian;
  String _relationship = 'parent';
  bool _isPrimary = true;

  final _firstCtrl = TextEditingController();
  final _lastCtrl = TextEditingController();
  final _emailCtrl = TextEditingController();
  final _phoneCtrl = TextEditingController();

  @override
  void initState() {
    super.initState();
    _loadGuardians();
  }

  Future<void> _loadGuardians() async {
    try {
      final guardians = await widget.deps.peopleApi.fetchGuardians(limit: 200);
      if (!mounted) return;
      setState(() {
        _guardians = guardians;
        _selectedGuardian = guardians.isEmpty ? null : guardians.first;
        _createNew = guardians.isEmpty;
        _loading = false;
      });
    } catch (_) {
      if (!mounted) return;
      setState(() {
        _loading = false;
        _error = 'Could not load parents.';
      });
    }
  }

  @override
  void dispose() {
    _firstCtrl.dispose();
    _lastCtrl.dispose();
    _emailCtrl.dispose();
    _phoneCtrl.dispose();
    super.dispose();
  }

  Future<void> _submit() async {
    if (!_createNew && _selectedGuardian == null) {
      setState(() => _error = 'Pick a parent, or create a new one.');
      return;
    }
    if (_createNew &&
        (_firstCtrl.text.trim().isEmpty ||
            _lastCtrl.text.trim().isEmpty ||
            _emailCtrl.text.trim().isEmpty)) {
      setState(() => _error = 'Parent first name, last name, and email are required.');
      return;
    }
    setState(() {
      _submitting = true;
      _error = null;
    });
    try {
      var guardian = _selectedGuardian;
      if (_createNew) {
        guardian = await widget.deps.peopleApi.createGuardian({
          'first_name': _firstCtrl.text.trim(),
          'last_name': _lastCtrl.text.trim(),
          'email': _emailCtrl.text.trim(),
          'phone_e164': _phoneCtrl.text.trim().isEmpty ? null : _phoneCtrl.text.trim(),
          'create_parent_login': true,
        });
      }
      await widget.deps.peopleApi.attachStudentGuardian(widget.studentId, {
        'guardian_id': guardian!.id,
        'relationship_type': _relationship,
        'is_primary_contact': _isPrimary,
      });
      if (mounted) Navigator.of(context).pop(true);
    } on AdminPeopleUnauthorized {
      setState(() => _error = 'Session expired.');
    } on AdminPeopleApiFailure catch (e) {
      setState(() => _error = e.message);
    } catch (_) {
      setState(() => _error = 'Could not link parent.');
    } finally {
      if (mounted) setState(() => _submitting = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Scaffold(
      appBar: AppBar(title: const Text('Link parent')),
      body: _loading
          ? const Center(child: CircularProgressIndicator())
          : ListView(
              padding: const EdgeInsets.all(16),
              children: [
                Text(
                  'Parent of ${widget.studentName}',
                  style: theme.textTheme.titleMedium?.copyWith(fontWeight: FontWeight.w700),
                ),
                const SizedBox(height: 4),
                Text(
                  'The parent email becomes their Parent app login.',
                  style: theme.textTheme.bodySmall?.copyWith(
                    color: theme.colorScheme.onSurfaceVariant,
                  ),
                ),
                const SizedBox(height: 16),
                SegmentedButton<bool>(
                  segments: const [
                    ButtonSegment(value: true, label: Text('New parent')),
                    ButtonSegment(value: false, label: Text('Existing parent')),
                  ],
                  selected: {_createNew},
                  onSelectionChanged: _submitting
                      ? null
                      : (s) => setState(() => _createNew = s.first),
                ),
                const SizedBox(height: 16),
                if (_createNew) ...[
                  TextField(
                    controller: _firstCtrl,
                    decoration: const InputDecoration(labelText: 'Parent first name'),
                    textInputAction: TextInputAction.next,
                  ),
                  const SizedBox(height: 12),
                  TextField(
                    controller: _lastCtrl,
                    decoration: const InputDecoration(labelText: 'Parent last name'),
                    textInputAction: TextInputAction.next,
                  ),
                  const SizedBox(height: 12),
                  TextField(
                    controller: _emailCtrl,
                    decoration: const InputDecoration(labelText: 'Parent email (login)'),
                    keyboardType: TextInputType.emailAddress,
                    textInputAction: TextInputAction.next,
                  ),
                  const SizedBox(height: 12),
                  TextField(
                    controller: _phoneCtrl,
                    decoration: const InputDecoration(labelText: 'Parent phone (optional)'),
                    keyboardType: TextInputType.phone,
                  ),
                ] else
                  DropdownButtonFormField<GuardianDetail>(
                    initialValue: _selectedGuardian,
                    items: _guardians
                        .map(
                          (g) => DropdownMenuItem(
                            value: g,
                            child: Text(
                              '${g.displayName}${g.email == null ? '' : ' · ${g.email}'}',
                            ),
                          ),
                        )
                        .toList(),
                    onChanged: _submitting ? null : (v) => setState(() => _selectedGuardian = v),
                    decoration: const InputDecoration(labelText: 'Existing parent'),
                  ),
                const SizedBox(height: 12),
                DropdownButtonFormField<String>(
                  initialValue: _relationship,
                  items: _relationshipOptions
                      .map((r) => DropdownMenuItem(value: r, child: Text(r[0].toUpperCase() + r.substring(1))))
                      .toList(),
                  onChanged: _submitting ? null : (v) => setState(() => _relationship = v ?? _relationship),
                  decoration: const InputDecoration(labelText: 'Relationship'),
                ),
                const SizedBox(height: 8),
                SwitchListTile(
                  contentPadding: EdgeInsets.zero,
                  title: const Text('Primary contact'),
                  subtitle: const Text('First person the school calls about this child'),
                  value: _isPrimary,
                  onChanged: _submitting ? null : (v) => setState(() => _isPrimary = v),
                ),
                if (_error != null) ...[
                  const SizedBox(height: 12),
                  ErrorBanner(message: _error!),
                ],
                const SizedBox(height: 24),
                FilledButton(
                  onPressed: _submitting ? null : _submit,
                  child: _submitting
                      ? const SizedBox(height: 20, width: 20, child: CircularProgressIndicator(strokeWidth: 2))
                      : const Text('Link parent'),
                ),
              ],
            ),
    );
  }
}
