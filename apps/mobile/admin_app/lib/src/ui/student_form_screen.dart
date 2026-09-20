import 'package:flutter/material.dart';

import '../academic/academic_models.dart';
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
  final _relationshipCtrl = TextEditingController(text: 'parent');
  final _parentFirstCtrl = TextEditingController();
  final _parentLastCtrl = TextEditingController();
  final _parentEmailCtrl = TextEditingController();
  final _parentPhoneCtrl = TextEditingController();

  bool _enrollOnCreate = true;
  bool _linkGuardianOnCreate = true;
  bool _createNewParent = true;
  bool _loadingOptions = true;
  bool _submitting = false;
  String? _error;

  List<AcademicYearItem> _years = const [];
  List<SchoolClassItem> _classes = const [];
  List<SectionItem> _sections = const [];
  List<GuardianDetail> _guardians = const [];

  AcademicYearItem? _year;
  SchoolClassItem? _clazz;
  SectionItem? _section;
  GuardianDetail? _guardian;

  @override
  void initState() {
    super.initState();
    final e = widget.existing;
    if (e != null) {
      _admissionCtrl.text = e.admissionNo;
      _firstCtrl.text = e.firstName;
      _middleCtrl.text = e.middleName ?? '';
      _lastCtrl.text = e.lastName;
      _enrollOnCreate = false;
      _linkGuardianOnCreate = false;
      _loadingOptions = false;
    } else {
      _loadOptions();
    }
  }

  Future<void> _loadOptions() async {
    try {
      _years = await widget.deps.academicApi.fetchAcademicYears();
      _classes = await widget.deps.academicApi.fetchClasses();
      _guardians = await widget.deps.peopleApi.fetchGuardians();
      _year = _years.isEmpty ? null : _years.first;
      _clazz = _classes.isEmpty ? null : _classes.first;
      _guardian = _guardians.isEmpty ? null : _guardians.first;
      _createNewParent = _guardians.isEmpty;
      if (_clazz != null) {
        _sections = await widget.deps.academicApi.fetchSections(classId: _clazz!.id);
        _section = _sections.isEmpty ? null : _sections.first;
      }
    } catch (_) {
      _error = 'Could not load enrollment options.';
    } finally {
      if (mounted) setState(() => _loadingOptions = false);
    }
  }

  Future<void> _onClassChanged(SchoolClassItem? value) async {
    setState(() {
      _clazz = value;
      _section = null;
      _sections = const [];
    });
    if (value == null) return;
    final sections = await widget.deps.academicApi.fetchSections(classId: value.id);
    if (!mounted) return;
    setState(() {
      _sections = sections;
      _section = sections.isEmpty ? null : sections.first;
    });
  }

  @override
  void dispose() {
    _admissionCtrl.dispose();
    _firstCtrl.dispose();
    _middleCtrl.dispose();
    _lastCtrl.dispose();
    _relationshipCtrl.dispose();
    _parentFirstCtrl.dispose();
    _parentLastCtrl.dispose();
    _parentEmailCtrl.dispose();
    _parentPhoneCtrl.dispose();
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
        if (_enrollOnCreate && (_year == null || _clazz == null || _section == null)) {
          setState(() {
            _error = 'Select academic year, class, and section to enroll.';
            _submitting = false;
          });
          return;
        }
        if (_linkGuardianOnCreate && _createNewParent) {
          if (_parentFirstCtrl.text.trim().isEmpty ||
              _parentLastCtrl.text.trim().isEmpty ||
              _parentEmailCtrl.text.trim().isEmpty) {
            setState(() {
              _error = 'Parent first name, last name, and email are required.';
              _submitting = false;
            });
            return;
          }
        }
        if (_linkGuardianOnCreate && !_createNewParent && _guardian == null) {
          setState(() {
            _error = 'Select an existing parent, or create a new one.';
            _submitting = false;
          });
          return;
        }

        final student = await widget.deps.peopleApi.createStudent({
          'admission_no': _admissionCtrl.text.trim(),
          'first_name': _firstCtrl.text.trim(),
          'middle_name': _middleCtrl.text.trim().isEmpty ? null : _middleCtrl.text.trim(),
          'last_name': _lastCtrl.text.trim(),
        });

        if (_enrollOnCreate) {
          await widget.deps.peopleApi.createEnrollment({
            'student_id': student.id,
            'academic_year_id': _year!.id,
            'class_id': _clazz!.id,
            'section_id': _section!.id,
            'starts_on': DateTime.now().toIso8601String().split('T').first,
          });
        }

        if (_linkGuardianOnCreate) {
          var guardian = _guardian;
          if (_createNewParent) {
            guardian = await widget.deps.peopleApi.createGuardian({
              'first_name': _parentFirstCtrl.text.trim(),
              'last_name': _parentLastCtrl.text.trim(),
              'email': _parentEmailCtrl.text.trim(),
              'phone_e164': _parentPhoneCtrl.text.trim().isEmpty ? null : _parentPhoneCtrl.text.trim(),
              'create_parent_login': true,
            });
          }
          await widget.deps.peopleApi.attachStudentGuardian(student.id, {
            'guardian_id': guardian!.id,
            'relationship_type': _relationshipCtrl.text.trim().isEmpty
                ? 'parent'
                : _relationshipCtrl.text.trim(),
            'is_primary_contact': true,
          });
        }
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
      body: _loadingOptions
          ? const Center(child: CircularProgressIndicator())
          : ListView(
              padding: const EdgeInsets.all(16),
              children: [
                if (!widget.isEdit)
                  TextField(
                    controller: _admissionCtrl,
                    decoration: const InputDecoration(labelText: 'Admission number / student ID'),
                    textInputAction: TextInputAction.next,
                  ),
                TextField(controller: _firstCtrl, decoration: const InputDecoration(labelText: 'First name')),
                TextField(
                  controller: _middleCtrl,
                  decoration: const InputDecoration(labelText: 'Middle name (optional)'),
                ),
                TextField(controller: _lastCtrl, decoration: const InputDecoration(labelText: 'Last name')),
                if (!widget.isEdit) ...[
                  const SizedBox(height: 16),
                  Text('Enrollment', style: Theme.of(context).textTheme.titleMedium),
                  SwitchListTile(
                    contentPadding: EdgeInsets.zero,
                    title: const Text('Enroll into a class/section now'),
                    value: _enrollOnCreate,
                    onChanged: _submitting ? null : (v) => setState(() => _enrollOnCreate = v),
                  ),
                  if (_enrollOnCreate) ...[
                    DropdownButtonFormField<AcademicYearItem>(
                      initialValue: _year,
                      items: _years
                          .map((y) => DropdownMenuItem(value: y, child: Text(y.name)))
                          .toList(),
                      onChanged: _submitting ? null : (v) => setState(() => _year = v),
                      decoration: const InputDecoration(labelText: 'Academic year'),
                    ),
                    DropdownButtonFormField<SchoolClassItem>(
                      initialValue: _clazz,
                      items: _classes
                          .map((c) => DropdownMenuItem(value: c, child: Text(c.name)))
                          .toList(),
                      onChanged: _submitting ? null : _onClassChanged,
                      decoration: const InputDecoration(labelText: 'Class'),
                    ),
                    DropdownButtonFormField<SectionItem>(
                      initialValue: _section,
                      items: _sections
                          .map((s) => DropdownMenuItem(value: s, child: Text(s.name)))
                          .toList(),
                      onChanged: _submitting ? null : (v) => setState(() => _section = v),
                      decoration: const InputDecoration(labelText: 'Section'),
                    ),
                  ],
                  const SizedBox(height: 16),
                  Text('Parent / guardian', style: Theme.of(context).textTheme.titleMedium),
                  const Text(
                    'The parent email becomes their Parent app login. Use the school directory password for first sign-in.',
                  ),
                  SwitchListTile(
                    contentPadding: EdgeInsets.zero,
                    title: const Text('Link parent/guardian now'),
                    value: _linkGuardianOnCreate,
                    onChanged: _submitting ? null : (v) => setState(() => _linkGuardianOnCreate = v),
                  ),
                  if (_linkGuardianOnCreate) ...[
                    SwitchListTile(
                      contentPadding: EdgeInsets.zero,
                      title: const Text('Create a new parent'),
                      subtitle: const Text('Turn off to pick an existing parent'),
                      value: _createNewParent,
                      onChanged: _submitting ? null : (v) => setState(() => _createNewParent = v),
                    ),
                    if (_createNewParent) ...[
                      TextField(
                        controller: _parentFirstCtrl,
                        decoration: const InputDecoration(labelText: 'Parent first name'),
                      ),
                      TextField(
                        controller: _parentLastCtrl,
                        decoration: const InputDecoration(labelText: 'Parent last name'),
                      ),
                      TextField(
                        controller: _parentEmailCtrl,
                        decoration: const InputDecoration(labelText: 'Parent email (login)'),
                        keyboardType: TextInputType.emailAddress,
                      ),
                      TextField(
                        controller: _parentPhoneCtrl,
                        decoration: const InputDecoration(labelText: 'Parent phone (optional)'),
                        keyboardType: TextInputType.phone,
                      ),
                    ] else
                      DropdownButtonFormField<GuardianDetail>(
                        initialValue: _guardian,
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
                        onChanged: _submitting ? null : (v) => setState(() => _guardian = v),
                        decoration: const InputDecoration(labelText: 'Existing parent'),
                      ),
                    TextField(
                      controller: _relationshipCtrl,
                      decoration: const InputDecoration(labelText: 'Relationship (e.g. parent)'),
                    ),
                  ],
                ],
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
