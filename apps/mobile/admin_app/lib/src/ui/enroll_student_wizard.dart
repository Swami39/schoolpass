import 'package:flutter/material.dart';
import 'package:schoolpass_design/schoolpass_design.dart';

import '../academic/academic_models.dart';
import '../app/admin_dependencies.dart';
import '../people/admin_people_api.dart';
import '../people/people_models.dart';
import 'admin_widgets.dart';

/// Three-step enrollment: 1) the child, 2) their class section,
/// 3) their parents. Can start with a section already chosen.
class EnrollStudentWizard extends StatefulWidget {
  const EnrollStudentWizard({
    required this.deps,
    this.initialYearId,
    this.initialClassId,
    this.initialSectionId,
    super.key,
  });

  final AdminDependencies deps;
  final String? initialYearId;
  final String? initialClassId;
  final String? initialSectionId;

  @override
  State<EnrollStudentWizard> createState() => _EnrollStudentWizardState();
}

class _ParentEntry {
  _ParentEntry({
    required this.isNew,
    this.existing,
    this.firstName = '',
    this.lastName = '',
    this.email = '',
    this.phone = '',
    this.relationship = 'parent',
    this.isPrimary = false,
  });

  bool isNew;
  GuardianDetail? existing;
  String firstName;
  String lastName;
  String email;
  String phone;
  String relationship;
  bool isPrimary;

  String get label => isNew ? '$firstName $lastName'.trim() : (existing?.displayName ?? 'Parent');
}

const _relationshipOptions = ['parent', 'mother', 'father', 'guardian', 'other'];

class _EnrollStudentWizardState extends State<EnrollStudentWizard> {
  int _step = 0;
  bool _loading = true;
  bool _submitting = false;
  String? _error;

  // Step 1: child
  final _admissionCtrl = TextEditingController();
  final _firstCtrl = TextEditingController();
  final _middleCtrl = TextEditingController();
  final _lastCtrl = TextEditingController();
  final _dobCtrl = TextEditingController();

  // Step 2: placement
  List<AcademicYearItem> _years = const [];
  List<SchoolClassItem> _classes = const [];
  List<SectionItem> _sections = const [];
  AcademicYearItem? _year;
  SchoolClassItem? _clazz;
  SectionItem? _section;

  // Step 3: parents
  List<GuardianDetail> _guardians = const [];
  final List<_ParentEntry> _parents = [];
  bool _addingParent = false;

  // add-parent form state
  bool _newParent = true;
  GuardianDetail? _pickedGuardian;
  String _rel = 'parent';
  bool _primary = true;
  final _pFirst = TextEditingController();
  final _pLast = TextEditingController();
  final _pEmail = TextEditingController();
  final _pPhone = TextEditingController();

  @override
  void initState() {
    super.initState();
    _bootstrap();
  }

  Future<void> _bootstrap() async {
    try {
      final results = await Future.wait([
        widget.deps.academicApi.fetchAcademicYears(),
        widget.deps.academicApi.fetchClasses(),
        widget.deps.peopleApi.fetchGuardians(limit: 200),
      ]);
      final years = results[0] as List<AcademicYearItem>;
      final classes = results[1] as List<SchoolClassItem>;
      if (!mounted) return;
      setState(() {
        _years = years;
        _classes = classes;
        _guardians = results[2] as List<GuardianDetail>;
        _year = _byId(years, widget.initialYearId) ?? (years.isEmpty ? null : years.first);
        _clazz = _byId(classes, widget.initialClassId) ?? (classes.isEmpty ? null : classes.first);
        _pickedGuardian = _guardians.isEmpty ? null : _guardians.first;
        _newParent = _guardians.isEmpty;
        _loading = false;
      });
      if (_clazz != null) await _loadSections(preselectId: widget.initialSectionId);
    } catch (_) {
      if (!mounted) return;
      setState(() {
        _loading = false;
        _error = 'Could not load enrollment options.';
      });
    }
  }

  T? _byId<T>(List<T> items, String? id) {
    if (id == null) {
      return null;
    }
    for (final item in items) {
      final itemId = (item as dynamic).id as String;
      if (itemId == id) return item;
    }
    return null;
  }

  Future<void> _loadSections({String? preselectId}) async {
    final clazz = _clazz;
    if (clazz == null) return;
    try {
      final sections = await widget.deps.academicApi.fetchSections(classId: clazz.id);
      if (!mounted) return;
      setState(() {
        _sections = sections;
        _section = _byId(sections, preselectId) ?? (sections.isEmpty ? null : sections.first);
      });
    } catch (_) {
      if (mounted) setState(() => _error = 'Could not load sections.');
    }
  }

  Future<void> _onClassChanged(SchoolClassItem? value) async {
    setState(() {
      _clazz = value;
      _section = null;
      _sections = const [];
    });
    await _loadSections();
  }

  @override
  void dispose() {
    _admissionCtrl.dispose();
    _firstCtrl.dispose();
    _middleCtrl.dispose();
    _lastCtrl.dispose();
    _dobCtrl.dispose();
    _pFirst.dispose();
    _pLast.dispose();
    _pEmail.dispose();
    _pPhone.dispose();
    super.dispose();
  }

  bool _validateStep() {
    if (_step == 0) {
      if (_admissionCtrl.text.trim().isEmpty ||
          _firstCtrl.text.trim().isEmpty ||
          _lastCtrl.text.trim().isEmpty) {
        setState(() => _error = 'Admission number, first name, and last name are required.');
        return false;
      }
    }
    if (_step == 1) {
      if (_year == null || _clazz == null || _section == null) {
        setState(() => _error = 'Pick an academic year, class, and section.');
        return false;
      }
    }
    setState(() => _error = null);
    return true;
  }

  void _next() {
    if (!_validateStep()) {
      return;
    }
    if (_step < 2) {
      setState(() => _step++);
    }
  }

  void _back() {
    if (_step > 0) {
      setState(() => _step--);
    } else {
      Navigator.of(context).pop();
    }
  }

  void _addParentEntry() {
    if (_newParent) {
      if (_pFirst.text.trim().isEmpty || _pLast.text.trim().isEmpty || _pEmail.text.trim().isEmpty) {
        setState(() => _error = 'Parent first name, last name, and email are required.');
        return;
      }
    } else if (_pickedGuardian == null) {
      setState(() => _error = 'Pick an existing parent.');
      return;
    }
    setState(() {
      _error = null;
      final entry = _ParentEntry(
        isNew: _newParent,
        existing: _newParent ? null : _pickedGuardian,
        firstName: _pFirst.text.trim(),
        lastName: _pLast.text.trim(),
        email: _pEmail.text.trim(),
        phone: _pPhone.text.trim(),
        relationship: _rel,
        isPrimary: _parents.isEmpty ? true : _primary,
      );
      if (_parents.isEmpty) entry.isPrimary = true;
      _parents.add(entry);
      _addingParent = false;
      _pFirst.clear();
      _pLast.clear();
      _pEmail.clear();
      _pPhone.clear();
      _rel = 'parent';
      _primary = false;
    });
  }

  Future<void> _submit() async {
    setState(() {
      _submitting = true;
      _error = null;
    });
    try {
      final student = await widget.deps.peopleApi.createStudent({
        'admission_no': _admissionCtrl.text.trim(),
        'first_name': _firstCtrl.text.trim(),
        'middle_name': _middleCtrl.text.trim().isEmpty ? null : _middleCtrl.text.trim(),
        'last_name': _lastCtrl.text.trim(),
        if (_dobCtrl.text.trim().isNotEmpty) 'date_of_birth': _dobCtrl.text.trim(),
      });
      await widget.deps.peopleApi.createEnrollment({
        'student_id': student.id,
        'academic_year_id': _year!.id,
        'class_id': _clazz!.id,
        'section_id': _section!.id,
        'starts_on': DateTime.now().toIso8601String().split('T').first,
      });
      for (final entry in _parents) {
        var guardian = entry.existing;
        guardian ??= await widget.deps.peopleApi.createGuardian({
          'first_name': entry.firstName,
          'last_name': entry.lastName,
          'email': entry.email,
          'phone_e164': entry.phone.isEmpty ? null : entry.phone,
          'create_parent_login': true,
        });
        await widget.deps.peopleApi.attachStudentGuardian(student.id, {
          'guardian_id': guardian.id,
          'relationship_type': entry.relationship,
          'is_primary_contact': entry.isPrimary,
        });
      }
      if (mounted) Navigator.of(context).pop(true);
    } on AdminPeopleUnauthorized {
      setState(() => _error = 'Session expired.');
    } on AdminPeopleApiFailure catch (e) {
      setState(() => _error = e.message);
    } catch (_) {
      setState(() => _error = 'Could not enroll the student.');
    } finally {
      if (mounted) setState(() => _submitting = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Scaffold(
      appBar: AppBar(
        title: const Text('Enroll student'),
        leading: IconButton(icon: const Icon(Icons.close), onPressed: () => Navigator.of(context).pop()),
      ),
      body: _loading
          ? const Center(child: CircularProgressIndicator())
          : Column(
              children: [
                _StepProgress(step: _step),
                Expanded(
                  child: ListView(
                    padding: const EdgeInsets.all(16),
                    children: [
                      if (_step == 0) _childStep(theme),
                      if (_step == 1) _placementStep(),
                      if (_step == 2) _parentsStep(theme),
                      if (_error != null) ...[
                        const SizedBox(height: 12),
                        ErrorBanner(message: _error!),
                      ],
                    ],
                  ),
                ),
                _BottomBar(
                  step: _step,
                  submitting: _submitting,
                  onBack: _back,
                  onNext: _next,
                  onFinish: _submit,
                ),
              ],
            ),
    );
  }

  Widget _childStep(ThemeData theme) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const SectionLabel('Step 1 of 3 — the child'),
        Text(
          'Basic details first — class and parents come next.',
          style: theme.textTheme.bodyMedium?.copyWith(color: theme.colorScheme.onSurfaceVariant),
        ),
        const SizedBox(height: 16),
        TextField(
          controller: _admissionCtrl,
          decoration: const InputDecoration(labelText: 'Admission number / student ID'),
          textInputAction: TextInputAction.next,
        ),
        const SizedBox(height: 12),
        TextField(controller: _firstCtrl, decoration: const InputDecoration(labelText: 'First name'), textInputAction: TextInputAction.next),
        const SizedBox(height: 12),
        TextField(controller: _middleCtrl, decoration: const InputDecoration(labelText: 'Middle name (optional)'), textInputAction: TextInputAction.next),
        const SizedBox(height: 12),
        TextField(controller: _lastCtrl, decoration: const InputDecoration(labelText: 'Last name'), textInputAction: TextInputAction.next),
        const SizedBox(height: 12),
        TextField(controller: _dobCtrl, decoration: const InputDecoration(labelText: 'Date of birth (YYYY-MM-DD, optional)'), keyboardType: TextInputType.datetime),
      ],
    );
  }

  Widget _placementStep() {
    final theme = Theme.of(context);
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const SectionLabel('Step 2 of 3 — class section'),
        Text(
          'The child will be enrolled here for the selected year.',
          style: theme.textTheme.bodyMedium?.copyWith(color: theme.colorScheme.onSurfaceVariant),
        ),
        const SizedBox(height: 16),
        DropdownButtonFormField<AcademicYearItem>(
          initialValue: _year,
          items: _years.map((y) => DropdownMenuItem(value: y, child: Text(y.name))).toList(),
          onChanged: (v) => setState(() => _year = v),
          decoration: const InputDecoration(labelText: 'Academic year'),
        ),
        const SizedBox(height: 12),
        DropdownButtonFormField<SchoolClassItem>(
          initialValue: _clazz,
          items: _classes.map((c) => DropdownMenuItem(value: c, child: Text(c.name))).toList(),
          onChanged: _onClassChanged,
          decoration: const InputDecoration(labelText: 'Class'),
        ),
        const SizedBox(height: 12),
        DropdownButtonFormField<SectionItem>(
          initialValue: _section,
          items: _sections.map((s) => DropdownMenuItem(value: s, child: Text('Section ${s.name}'))).toList(),
          onChanged: (v) => setState(() => _section = v),
          decoration: const InputDecoration(labelText: 'Section'),
        ),
      ],
    );
  }

  Widget _parentsStep(ThemeData theme) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const SectionLabel('Step 3 of 3 — parents'),
        Text(
          'Add one or more parents. Each new parent gets a Parent app login from their email.',
          style: theme.textTheme.bodyMedium?.copyWith(color: theme.colorScheme.onSurfaceVariant),
        ),
        const SizedBox(height: 16),
        for (int i = 0; i < _parents.length; i++)
          Padding(
            padding: const EdgeInsets.only(bottom: 8),
            child: Panel(
              padding: const EdgeInsets.all(12),
              child: Row(
                children: [
                  Container(
                    width: 40,
                    height: 40,
                    decoration: BoxDecoration(
                      color: DesignColors.brandSoft,
                      borderRadius: BorderRadius.circular(12),
                    ),
                    child: const Icon(
                      Icons.family_restroom_outlined,
                      color: DesignColors.brandInk,
                    ),
                  ),
                  const SizedBox(width: 12),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          _parents[i].label.isEmpty ? 'Parent ${i + 1}' : _parents[i].label,
                          style: const TextStyle(
                            fontWeight: FontWeight.w700,
                            fontSize: 14,
                            color: DesignColors.ink,
                          ),
                        ),
                        const SizedBox(height: 2),
                        Text(
                          '${_parents[i].relationship}${_parents[i].isPrimary ? ' · primary contact' : ''}',
                          style: const TextStyle(
                            fontSize: 12,
                            color: DesignColors.ink2,
                          ),
                        ),
                      ],
                    ),
                  ),
                  IconButton(
                    icon: const Icon(Icons.delete_outline),
                    onPressed: () => setState(() => _parents.removeAt(i)),
                  ),
                ],
              ),
            ),
          ),
        if (_addingParent)
          Panel(
            child: Column(
              children: [
                  SegmentedButton<bool>(
                    segments: const [
                      ButtonSegment(value: true, label: Text('New parent')),
                      ButtonSegment(value: false, label: Text('Existing')),
                    ],
                    selected: {_newParent},
                    onSelectionChanged: (s) => setState(() => _newParent = s.first),
                  ),
                  const SizedBox(height: 12),
                  if (_newParent) ...[
                    TextField(controller: _pFirst, decoration: const InputDecoration(labelText: 'First name')),
                    const SizedBox(height: 12),
                    TextField(controller: _pLast, decoration: const InputDecoration(labelText: 'Last name')),
                    const SizedBox(height: 12),
                    TextField(controller: _pEmail, decoration: const InputDecoration(labelText: 'Email (login)'), keyboardType: TextInputType.emailAddress),
                    const SizedBox(height: 12),
                    TextField(controller: _pPhone, decoration: const InputDecoration(labelText: 'Phone (optional)'), keyboardType: TextInputType.phone),
                  ] else
                    DropdownButtonFormField<GuardianDetail>(
                      initialValue: _pickedGuardian,
                      items: _guardians
                          .map((g) => DropdownMenuItem(
                                value: g,
                                child: Text('${g.displayName}${g.email == null ? '' : ' · ${g.email}'}'),
                              ))
                          .toList(),
                      onChanged: (v) => setState(() => _pickedGuardian = v),
                      decoration: const InputDecoration(labelText: 'Existing parent'),
                    ),
                  const SizedBox(height: 12),
                  DropdownButtonFormField<String>(
                    initialValue: _rel,
                    items: _relationshipOptions
                        .map((r) => DropdownMenuItem(value: r, child: Text(r[0].toUpperCase() + r.substring(1))))
                        .toList(),
                    onChanged: (v) => setState(() => _rel = v ?? _rel),
                    decoration: const InputDecoration(labelText: 'Relationship'),
                  ),
                  if (_parents.isNotEmpty)
                    SwitchListTile(
                      contentPadding: EdgeInsets.zero,
                      title: const Text('Primary contact'),
                      value: _primary,
                      onChanged: (v) => setState(() => _primary = v),
                    ),
                  const SizedBox(height: 8),
                  Row(
                    children: [
                      Expanded(
                        child: OutlinedButton(
                          onPressed: () => setState(() => _addingParent = false),
                          child: const Text('Cancel'),
                        ),
                      ),
                      const SizedBox(width: 12),
                      Expanded(
                        child: PrimaryButton(
                          label: 'Add parent',
                          onPressed: _addParentEntry,
                        ),
                      ),
                    ],
                  ),
                ],
              ),
          )
        else
          OutlinedButton.icon(
            onPressed: () => setState(() => _addingParent = true),
            icon: const Icon(Icons.add),
            label: const Text('Add parent'),
          ),
        if (_parents.isEmpty && !_addingParent) ...[
          const SizedBox(height: 12),
          Text(
            'No parents added yet — you can finish now and link parents later from the section.',
            style: theme.textTheme.bodySmall?.copyWith(color: theme.colorScheme.onSurfaceVariant),
          ),
        ],
      ],
    );
  }
}

class _StepProgress extends StatelessWidget {
  const _StepProgress({required this.step});

  final int step;

  static const _labels = ['Child', 'Class', 'Parents'];

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.fromLTRB(16, 12, 16, 12),
      decoration: const BoxDecoration(
        border: Border(bottom: BorderSide(color: DesignColors.line)),
      ),
      child: Row(
        children: [
          for (int i = 0; i < _labels.length; i++) ...[
            _Dot(index: i, current: step),
            const SizedBox(width: 8),
            Text(
              _labels[i],
              style: TextStyle(
                fontWeight: i == step ? FontWeight.w800 : FontWeight.w500,
                color: i <= step ? DesignColors.brandInk : DesignColors.ink3,
              ),
            ),
            if (i < _labels.length - 1) ...[
              const SizedBox(width: 8),
              const Expanded(child: Divider(color: DesignColors.line2)),
              const SizedBox(width: 8),
            ],
          ],
        ],
      ),
    );
  }
}

class _Dot extends StatelessWidget {
  const _Dot({required this.index, required this.current});

  final int index;
  final int current;

  @override
  Widget build(BuildContext context) {
    final status = context.status;
    final done = index < current;
    final active = index == current;
    return Container(
      width: 28,
      height: 28,
      decoration: BoxDecoration(
        shape: BoxShape.circle,
        color: done
            ? status.softOf(StatusKind.present)
            : active
                ? DesignColors.brand
                : status.softOf(StatusKind.neutral),
      ),
      child: Center(
        child: done
            ? Icon(Icons.check, size: 16, color: status.of(StatusKind.present))
            : Text(
                '${index + 1}',
                style: TextStyle(
                  color: active
                      ? Colors.white
                      : status.of(StatusKind.neutral),
                  fontWeight: FontWeight.w700,
                  fontSize: 13,
                ),
              ),
      ),
    );
  }
}

class _BottomBar extends StatelessWidget {
  const _BottomBar({
    required this.step,
    required this.submitting,
    required this.onBack,
    required this.onNext,
    required this.onFinish,
  });

  final int step;
  final bool submitting;
  final VoidCallback onBack;
  final VoidCallback onNext;
  final VoidCallback onFinish;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.fromLTRB(16, 12, 16, 20),
      decoration: const BoxDecoration(
        border: Border(top: BorderSide(color: DesignColors.line)),
      ),
      child: Row(
        children: [
          Expanded(
            child: OutlinedButton(
              onPressed: submitting ? null : onBack,
              child: Text(step == 0 ? 'Cancel' : 'Back'),
            ),
          ),
          const SizedBox(width: 12),
          Expanded(
            flex: 2,
            child: submitting
                ? const PrimaryButton(label: 'Enrolling…', onPressed: null)
                : PrimaryButton(
                    label: step == 2 ? 'Enroll student' : 'Continue',
                    onPressed: step == 2 ? onFinish : onNext,
                  ),
          ),
        ],
      ),
    );
  }
}
