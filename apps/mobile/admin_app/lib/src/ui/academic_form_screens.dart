import 'package:flutter/material.dart';

import '../academic/academic_models.dart';
import '../academic/admin_academic_api.dart';
import '../app/admin_dependencies.dart';
import '../people/people_models.dart';
import 'admin_widgets.dart';

class AcademicYearFormScreen extends StatefulWidget {
  const AcademicYearFormScreen({required this.deps, super.key});

  final AdminDependencies deps;

  @override
  State<AcademicYearFormScreen> createState() => _AcademicYearFormScreenState();
}

class _AcademicYearFormScreenState extends State<AcademicYearFormScreen> {
  final _code = TextEditingController();
  final _name = TextEditingController();
  final _startsOn = TextEditingController(text: DateTime.now().toIso8601String().split('T').first);
  final _endsOn = TextEditingController(
    text: DateTime(DateTime.now().year + 1, 3, 31).toIso8601String().split('T').first,
  );
  bool _submitting = false;
  String? _error;

  @override
  void dispose() {
    _code.dispose();
    _name.dispose();
    _startsOn.dispose();
    _endsOn.dispose();
    super.dispose();
  }

  Future<void> _submit() async {
    setState(() {
      _submitting = true;
      _error = null;
    });
    try {
      await widget.deps.academicApi.createAcademicYear({
        'code': _code.text.trim(),
        'name': _name.text.trim(),
        'starts_on': _startsOn.text.trim(),
        'ends_on': _endsOn.text.trim(),
        'status': 'active',
      });
      if (mounted) Navigator.of(context).pop(true);
    } on AdminAcademicUnauthorized {
      setState(() => _error = 'Session expired.');
    } on AdminAcademicApiFailure catch (e) {
      setState(() => _error = e.message);
    } catch (_) {
      setState(() => _error = 'Could not create academic year.');
    } finally {
      if (mounted) setState(() => _submitting = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('New academic year')),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          TextField(controller: _code, decoration: const InputDecoration(labelText: 'Code (e.g. 2026-27)')),
          const SizedBox(height: 12),
          TextField(controller: _name, decoration: const InputDecoration(labelText: 'Name')),
          const SizedBox(height: 12),
          TextField(controller: _startsOn, decoration: const InputDecoration(labelText: 'Starts on (YYYY-MM-DD)')),
          const SizedBox(height: 12),
          TextField(controller: _endsOn, decoration: const InputDecoration(labelText: 'Ends on (YYYY-MM-DD)')),
          if (_error != null) ...[
            const SizedBox(height: 12),
            ErrorBanner(message: _error!),
          ],
          const SizedBox(height: 24),
          FilledButton(
            onPressed: _submitting ? null : _submit,
            child: _submitting
                ? const SizedBox(height: 20, width: 20, child: CircularProgressIndicator(strokeWidth: 2))
                : const Text('Create'),
          ),
        ],
      ),
    );
  }
}

class SchoolClassFormScreen extends StatefulWidget {
  const SchoolClassFormScreen({required this.deps, super.key});

  final AdminDependencies deps;

  @override
  State<SchoolClassFormScreen> createState() => _SchoolClassFormScreenState();
}

class _SchoolClassFormScreenState extends State<SchoolClassFormScreen> {
  final _code = TextEditingController();
  final _name = TextEditingController();
  final _sectionName = TextEditingController(text: 'A');
  bool _createSection = true;
  bool _submitting = false;
  String? _error;

  @override
  void dispose() {
    _code.dispose();
    _name.dispose();
    _sectionName.dispose();
    super.dispose();
  }

  Future<void> _submit() async {
    if (_code.text.trim().isEmpty || _name.text.trim().isEmpty) {
      setState(() => _error = 'Code and name are required.');
      return;
    }
    setState(() {
      _submitting = true;
      _error = null;
    });
    try {
      final clazz = await widget.deps.academicApi.createClass({
        'code': _code.text.trim(),
        'name': _name.text.trim(),
        'status': 'active',
      });
      if (_createSection && _sectionName.text.trim().isNotEmpty) {
        await widget.deps.academicApi.createSection({
          'class_id': clazz.id,
          'name': _sectionName.text.trim(),
          'status': 'active',
        });
      }
      if (mounted) Navigator.of(context).pop(true);
    } on AdminAcademicUnauthorized {
      setState(() => _error = 'Session expired.');
    } on AdminAcademicApiFailure catch (e) {
      setState(() => _error = e.message);
    } catch (_) {
      setState(() => _error = 'Could not create class.');
    } finally {
      if (mounted) setState(() => _submitting = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('New class')),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          TextField(controller: _code, decoration: const InputDecoration(labelText: 'Code (e.g. 10)')),
          const SizedBox(height: 12),
          TextField(controller: _name, decoration: const InputDecoration(labelText: 'Name (e.g. Class 10)')),
          const SizedBox(height: 8),
          SwitchListTile(
            title: const Text('Also create a section'),
            value: _createSection,
            onChanged: _submitting ? null : (v) => setState(() => _createSection = v),
          ),
          if (_createSection) ...[
            const SizedBox(height: 4),
            TextField(
              controller: _sectionName,
              decoration: const InputDecoration(labelText: 'Section name (e.g. A)'),
            ),
          ],
          if (_error != null) ...[
            const SizedBox(height: 12),
            ErrorBanner(message: _error!),
          ],
          const SizedBox(height: 24),
          FilledButton(
            onPressed: _submitting ? null : _submit,
            child: _submitting
                ? const SizedBox(height: 20, width: 20, child: CircularProgressIndicator(strokeWidth: 2))
                : const Text('Create class'),
          ),
        ],
      ),
    );
  }
}

class SectionFormScreen extends StatefulWidget {
  const SectionFormScreen({required this.deps, this.initialClassId, super.key});

  final AdminDependencies deps;
  final String? initialClassId;

  @override
  State<SectionFormScreen> createState() => _SectionFormScreenState();
}

class _SectionFormScreenState extends State<SectionFormScreen> {
  final _name = TextEditingController();
  List<SchoolClassItem> _classes = const [];
  SchoolClassItem? _clazz;
  bool _loading = true;
  bool _submitting = false;
  String? _error;

  @override
  void initState() {
    super.initState();
    _bootstrap();
  }

  Future<void> _bootstrap() async {
    try {
      _classes = await widget.deps.academicApi.fetchClasses();
      SchoolClassItem? preselected;
      if (widget.initialClassId != null) {
        for (final c in _classes) {
          if (c.id == widget.initialClassId) preselected = c;
        }
      }
      _clazz = preselected ?? (_classes.isEmpty ? null : _classes.first);
    } catch (_) {
      _error = 'Could not load classes.';
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  @override
  void dispose() {
    _name.dispose();
    super.dispose();
  }

  Future<void> _submit() async {
    if (_clazz == null || _name.text.trim().isEmpty) {
      setState(() => _error = 'Class and section name are required.');
      return;
    }
    setState(() {
      _submitting = true;
      _error = null;
    });
    try {
      await widget.deps.academicApi.createSection({
        'class_id': _clazz!.id,
        'name': _name.text.trim(),
        'status': 'active',
      });
      if (mounted) Navigator.of(context).pop(true);
    } on AdminAcademicUnauthorized {
      setState(() => _error = 'Session expired.');
    } on AdminAcademicApiFailure catch (e) {
      setState(() => _error = e.message);
    } catch (_) {
      setState(() => _error = 'Could not create section.');
    } finally {
      if (mounted) setState(() => _submitting = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('New section')),
      body: _loading
          ? const Center(child: CircularProgressIndicator())
          : ListView(
              padding: const EdgeInsets.all(16),
              children: [
                DropdownButtonFormField<SchoolClassItem>(
                  initialValue: _clazz,
                  items: _classes
                      .map(
                        (c) => DropdownMenuItem(
                          value: c,
                          child: Text('${c.name} (${c.code})'),
                        ),
                      )
                      .toList(),
                  onChanged: _submitting ? null : (v) => setState(() => _clazz = v),
                  decoration: const InputDecoration(labelText: 'Class'),
                ),
                const SizedBox(height: 12),
                TextField(controller: _name, decoration: const InputDecoration(labelText: 'Section name')),
                if (_error != null) ...[
                  const SizedBox(height: 12),
                  ErrorBanner(message: _error!),
                ],
                const SizedBox(height: 24),
                FilledButton(
                  onPressed: _submitting ? null : _submit,
                  child: _submitting
                      ? const SizedBox(height: 20, width: 20, child: CircularProgressIndicator(strokeWidth: 2))
                      : const Text('Create section'),
                ),
              ],
            ),
    );
  }
}

class SubjectFormScreen extends StatefulWidget {
  const SubjectFormScreen({required this.deps, super.key});

  final AdminDependencies deps;

  @override
  State<SubjectFormScreen> createState() => _SubjectFormScreenState();
}

class _SubjectFormScreenState extends State<SubjectFormScreen> {
  final _code = TextEditingController();
  final _name = TextEditingController();
  bool _submitting = false;
  String? _error;

  @override
  void dispose() {
    _code.dispose();
    _name.dispose();
    super.dispose();
  }

  Future<void> _submit() async {
    setState(() {
      _submitting = true;
      _error = null;
    });
    try {
      await widget.deps.academicApi.createSubject({
        'code': _code.text.trim(),
        'name': _name.text.trim(),
        'status': 'active',
      });
      if (mounted) Navigator.of(context).pop(true);
    } on AdminAcademicUnauthorized {
      setState(() => _error = 'Session expired.');
    } on AdminAcademicApiFailure catch (e) {
      setState(() => _error = e.message);
    } catch (_) {
      setState(() => _error = 'Could not create subject.');
    } finally {
      if (mounted) setState(() => _submitting = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('New subject')),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          TextField(controller: _code, decoration: const InputDecoration(labelText: 'Code (e.g. MATH)')),
          const SizedBox(height: 12),
          TextField(controller: _name, decoration: const InputDecoration(labelText: 'Name')),
          if (_error != null) ...[
            const SizedBox(height: 12),
            ErrorBanner(message: _error!),
          ],
          const SizedBox(height: 24),
          FilledButton(
            onPressed: _submitting ? null : _submit,
            child: _submitting
                ? const SizedBox(height: 20, width: 20, child: CircularProgressIndicator(strokeWidth: 2))
                : const Text('Create subject'),
          ),
        ],
      ),
    );
  }
}

class TeacherAssignmentFormScreen extends StatefulWidget {
  const TeacherAssignmentFormScreen({
    required this.deps,
    this.initialClassId,
    this.initialSectionId,
    super.key,
  });

  final AdminDependencies deps;
  final String? initialClassId;
  final String? initialSectionId;

  @override
  State<TeacherAssignmentFormScreen> createState() => _TeacherAssignmentFormScreenState();
}

class _TeacherAssignmentFormScreenState extends State<TeacherAssignmentFormScreen> {
  List<StaffListItem> _teachers = const [];
  List<AcademicYearItem> _years = const [];
  List<SchoolClassItem> _classes = const [];
  List<SectionItem> _sections = const [];
  List<SubjectItem> _subjects = const [];

  StaffListItem? _teacher;
  AcademicYearItem? _year;
  SchoolClassItem? _clazz;
  SectionItem? _section;
  SubjectItem? _subject;
  String _role = 'class_teacher';
  bool _loading = true;
  bool _submitting = false;
  String? _error;

  @override
  void initState() {
    super.initState();
    _bootstrap();
  }

  Future<void> _bootstrap() async {
    try {
      final staff = await widget.deps.peopleApi.fetchStaff(staffType: 'teacher');
      _teachers = staff;
      _years = await widget.deps.academicApi.fetchAcademicYears();
      _classes = await widget.deps.academicApi.fetchClasses();
      _subjects = await widget.deps.academicApi.fetchSubjects();
      _teacher = _teachers.isEmpty ? null : _teachers.first;
      _year = _years.isEmpty ? null : _years.first;
      _clazz = _findClass(widget.initialClassId) ?? (_classes.isEmpty ? null : _classes.first);
      if (_clazz != null) {
        _sections = await widget.deps.academicApi.fetchSections(classId: _clazz!.id);
        _section = _findSection(widget.initialSectionId) ?? (_sections.isEmpty ? null : _sections.first);
      }
      _subject = _subjects.isEmpty ? null : _subjects.first;
    } catch (_) {
      _error = 'Could not load assignment options.';
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  SchoolClassItem? _findClass(String? id) {
    if (id == null) return null;
    for (final c in _classes) {
      if (c.id == id) return c;
    }
    return null;
  }

  SectionItem? _findSection(String? id) {
    if (id == null) return null;
    for (final s in _sections) {
      if (s.id == id) return s;
    }
    return null;
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

  Future<void> _submit() async {
    if (_teacher == null || _year == null || _section == null) {
      setState(() => _error = 'Teacher, academic year, and section are required.');
      return;
    }
    // Staff list items usually carry user_id already; fall back to a detail fetch.
    setState(() {
      _submitting = true;
      _error = null;
    });
    try {
      final teacherUserId = _teacher!.userId ??
          (await widget.deps.peopleApi.fetchStaffMember(_teacher!.id)).userId;
      if (teacherUserId == null) {
        setState(() => _error = 'Could not resolve this teacher\u2019s login id.');
        return;
      }
      await widget.deps.academicApi.createTeacherAssignment({
        'teacher_user_id': teacherUserId,
        'academic_year_id': _year!.id,
        'section_id': _section!.id,
        if (_subject != null) 'subject_id': _subject!.id,
        'assignment_role': _role,
        'status': 'active',
      });
      if (mounted) Navigator.of(context).pop(true);
    } on AdminAcademicUnauthorized {
      setState(() => _error = 'Session expired.');
    } on AdminAcademicApiFailure catch (e) {
      setState(() => _error = e.message);
    } catch (_) {
      setState(() => _error = 'Could not create teacher assignment.');
    } finally {
      if (mounted) setState(() => _submitting = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Assign teacher')),
      body: _loading
          ? const Center(child: CircularProgressIndicator())
          : ListView(
              padding: const EdgeInsets.all(16),
              children: [
                DropdownButtonFormField<StaffListItem>(
                  initialValue: _teacher,
                  items: _teachers
                      .map(
                        (t) => DropdownMenuItem(
                          value: t,
                          child: Text(t.email ?? t.employeeCode ?? 'Teacher'),
                        ),
                      )
                      .toList(),
                  onChanged: _submitting ? null : (v) => setState(() => _teacher = v),
                  decoration: const InputDecoration(labelText: 'Teacher'),
                ),
                const SizedBox(height: 12),
                DropdownButtonFormField<AcademicYearItem>(
                  initialValue: _year,
                  items: _years
                      .map((y) => DropdownMenuItem(value: y, child: Text(y.name)))
                      .toList(),
                  onChanged: _submitting ? null : (v) => setState(() => _year = v),
                  decoration: const InputDecoration(labelText: 'Academic year'),
                ),
                const SizedBox(height: 12),
                DropdownButtonFormField<SchoolClassItem>(
                  initialValue: _clazz,
                  items: _classes
                      .map((c) => DropdownMenuItem(value: c, child: Text('${c.name} (${c.code})')))
                      .toList(),
                  onChanged: _submitting ? null : _onClassChanged,
                  decoration: const InputDecoration(labelText: 'Class'),
                ),
                const SizedBox(height: 12),
                DropdownButtonFormField<SectionItem>(
                  initialValue: _section,
                  items: _sections
                      .map((s) => DropdownMenuItem(value: s, child: Text(s.name)))
                      .toList(),
                  onChanged: _submitting ? null : (v) => setState(() => _section = v),
                  decoration: const InputDecoration(labelText: 'Section'),
                ),
                const SizedBox(height: 12),
                DropdownButtonFormField<SubjectItem>(
                  initialValue: _subject,
                  items: [
                    const DropdownMenuItem<SubjectItem>(value: null, child: Text('No subject')),
                    ..._subjects.map(
                      (s) => DropdownMenuItem(value: s, child: Text('${s.name} (${s.code})')),
                    ),
                  ],
                  onChanged: _submitting ? null : (v) => setState(() => _subject = v),
                  decoration: const InputDecoration(labelText: 'Subject (optional)'),
                ),
                const SizedBox(height: 12),
                DropdownButtonFormField<String>(
                  initialValue: _role,
                  items: const [
                    DropdownMenuItem(value: 'class_teacher', child: Text('Class teacher')),
                    DropdownMenuItem(value: 'subject_teacher', child: Text('Subject teacher')),
                  ],
                  onChanged: _submitting ? null : (v) => setState(() => _role = v ?? _role),
                  decoration: const InputDecoration(labelText: 'Role'),
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
                      : const Text('Create assignment'),
                ),
              ],
            ),
    );
  }
}
