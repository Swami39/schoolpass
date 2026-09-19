import 'package:flutter/material.dart';

import '../academic/academic_models.dart';
import '../app/admin_dependencies.dart';
import '../operations/operations_models.dart';
import '../people/admin_people_api.dart';
import '../people/people_models.dart';
import 'student_form_screen.dart';

class StudentDetailScreen extends StatefulWidget {
  const StudentDetailScreen({required this.deps, required this.studentId, super.key});

  final AdminDependencies deps;
  final String studentId;

  @override
  State<StudentDetailScreen> createState() => _StudentDetailScreenState();
}

class _StudentDetailScreenState extends State<StudentDetailScreen> {
  StudentDetail? _student;
  List<EnrollmentDetail> _enrollments = const [];
  List<StudentGuardianLink> _guardianLinks = const [];
  List<CardAssignmentItem> _cardAssignments = const [];
  List<GuardianDetail> _allGuardians = const [];
  bool _loading = true;
  String? _error;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      _student = await widget.deps.peopleApi.fetchStudent(widget.studentId);
      _enrollments = await widget.deps.peopleApi.fetchStudentEnrollments(widget.studentId);
      _guardianLinks = await widget.deps.peopleApi.fetchStudentGuardians(widget.studentId);
      _cardAssignments = await widget.deps.operationsApi.fetchStudentCardAssignments(widget.studentId);
    } on AdminPeopleUnauthorized {
      _error = 'Session expired.';
    } on AdminPeopleApiFailure catch (e) {
      _error = e.message;
    } catch (_) {
      _error = 'Could not load student.';
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  Future<void> _edit() async {
    if (_student == null) return;
    final changed = await Navigator.of(context).push<bool>(
      MaterialPageRoute(builder: (_) => StudentFormScreen(deps: widget.deps, existing: _student)),
    );
    if (changed == true) _load();
  }

  Future<void> _addEnrollment() async {
    final years = await widget.deps.academicApi.fetchAcademicYears();
    if (years.isEmpty) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('No academic years configured.')));
      }
      return;
    }
    AcademicYearItem? year = years.first;
    SchoolClassItem? clazz;
    SectionItem? section;
    if (!mounted) return;
    await showDialog<void>(
      context: context,
      builder: (context) => StatefulBuilder(
        builder: (context, setLocal) {
          return AlertDialog(
            title: const Text('New enrollment'),
            content: SingleChildScrollView(
              child: Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                  DropdownButton<AcademicYearItem>(
                    value: year,
                    items: years.map((y) => DropdownMenuItem(value: y, child: Text(y.name))).toList(),
                    onChanged: (v) => setLocal(() => year = v),
                  ),
                  FutureBuilder<List<SchoolClassItem>>(
                    future: widget.deps.academicApi.fetchClasses(),
                    builder: (context, snap) {
                      final classes = snap.data ?? const [];
                      return DropdownButton<SchoolClassItem>(
                        hint: const Text('Class'),
                        value: clazz,
                        items: classes.map((c) => DropdownMenuItem(value: c, child: Text(c.name))).toList(),
                        onChanged: (v) => setLocal(() {
                          clazz = v;
                          section = null;
                        }),
                      );
                    },
                  ),
                  if (clazz != null)
                    FutureBuilder<List<SectionItem>>(
                      future: widget.deps.academicApi.fetchSections(classId: clazz!.id),
                      builder: (context, snap) {
                        final sections = snap.data ?? const [];
                        return DropdownButton<SectionItem>(
                          hint: const Text('Section'),
                          value: section,
                          items: sections.map((s) => DropdownMenuItem(value: s, child: Text(s.name))).toList(),
                          onChanged: (v) => setLocal(() => section = v),
                        );
                      },
                    ),
                ],
              ),
            ),
            actions: [
              TextButton(onPressed: () => Navigator.pop(context), child: const Text('Cancel')),
              FilledButton(
                onPressed: () async {
                  if (year == null || clazz == null || section == null) return;
                  try {
                    await widget.deps.peopleApi.createEnrollment({
                      'student_id': widget.studentId,
                      'academic_year_id': year!.id,
                      'class_id': clazz!.id,
                      'section_id': section!.id,
                      'starts_on': DateTime.now().toIso8601String().split('T').first,
                    });
                    if (context.mounted) Navigator.pop(context);
                    _load();
                  } on AdminPeopleApiFailure catch (e) {
                    if (context.mounted) {
                      ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(e.message)));
                    }
                  }
                },
                child: const Text('Create'),
              ),
            ],
          );
        },
      ),
    );
  }

  Future<void> _moveEnrollment(EnrollmentDetail enrollment) async {
    final classes = await widget.deps.academicApi.fetchClasses();
    SchoolClassItem? clazz;
    SectionItem? section;
    if (!mounted) return;
    await showDialog<void>(
      context: context,
      builder: (context) => StatefulBuilder(
        builder: (context, setLocal) => AlertDialog(
          title: const Text('Move enrollment'),
          content: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              DropdownButton<SchoolClassItem>(
                hint: const Text('New class'),
                items: classes.map((c) => DropdownMenuItem(value: c, child: Text(c.name))).toList(),
                onChanged: (v) => setLocal(() {
                  clazz = v;
                  section = null;
                }),
              ),
              if (clazz != null)
                FutureBuilder<List<SectionItem>>(
                  future: widget.deps.academicApi.fetchSections(classId: clazz!.id),
                  builder: (context, snap) {
                    final sections = snap.data ?? const [];
                    return DropdownButton<SectionItem>(
                      hint: const Text('New section'),
                      items: sections.map((s) => DropdownMenuItem(value: s, child: Text(s.name))).toList(),
                      onChanged: (v) => setLocal(() => section = v),
                    );
                  },
                ),
            ],
          ),
          actions: [
            TextButton(onPressed: () => Navigator.pop(context), child: const Text('Cancel')),
            FilledButton(
              onPressed: () async {
                if (clazz == null || section == null) return;
                try {
                  await widget.deps.peopleApi.updateEnrollment(enrollment.id, {
                    'class_id': clazz!.id,
                    'section_id': section!.id,
                  });
                  if (context.mounted) Navigator.pop(context);
                  _load();
                } on AdminPeopleApiFailure catch (e) {
                  if (context.mounted) {
                    ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(e.message)));
                  }
                }
              },
              child: const Text('Update'),
            ),
          ],
        ),
      ),
    );
  }

  Future<void> _closeEnrollment(EnrollmentDetail enrollment) async {
    try {
      await widget.deps.peopleApi.closeEnrollment(enrollment.id, {
        'ends_on': DateTime.now().toIso8601String().split('T').first,
        'status': 'completed',
      });
      _load();
    } on AdminPeopleApiFailure catch (e) {
      if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(e.message)));
    }
  }

  Future<void> _linkGuardian() async {
    _allGuardians = await widget.deps.peopleApi.fetchGuardians();
    GuardianDetail? selected;
    final relationshipCtrl = TextEditingController(text: 'parent');
    if (!mounted) return;
    await showDialog<void>(
      context: context,
      builder: (context) => StatefulBuilder(
        builder: (context, setLocal) => AlertDialog(
          title: const Text('Link guardian'),
          content: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              DropdownButton<GuardianDetail>(
                hint: const Text('Guardian'),
                items: _allGuardians
                    .map((g) => DropdownMenuItem(value: g, child: Text(g.displayName)))
                    .toList(),
                onChanged: (v) => setLocal(() => selected = v),
              ),
              TextField(controller: relationshipCtrl, decoration: const InputDecoration(labelText: 'Relationship')),
            ],
          ),
          actions: [
            TextButton(onPressed: () => Navigator.pop(context), child: const Text('Cancel')),
            FilledButton(
              onPressed: () async {
                if (selected == null) return;
                try {
                  await widget.deps.peopleApi.attachStudentGuardian(widget.studentId, {
                    'guardian_id': selected!.id,
                    'relationship_type': relationshipCtrl.text.trim(),
                    'is_primary_contact': false,
                  });
                  if (context.mounted) Navigator.pop(context);
                  _load();
                } on AdminPeopleApiFailure catch (e) {
                  if (context.mounted) {
                    ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(e.message)));
                  }
                }
              },
              child: const Text('Link'),
            ),
          ],
        ),
      ),
    );
    relationshipCtrl.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Student'),
        actions: [
          IconButton(onPressed: _load, icon: const Icon(Icons.refresh)),
          if (_student != null) IconButton(onPressed: _edit, icon: const Icon(Icons.edit)),
        ],
      ),
      body: _loading
          ? const Center(child: CircularProgressIndicator())
          : _error != null
              ? Center(
                  child: Column(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      Text(_error!),
                      FilledButton(onPressed: _load, child: const Text('Retry')),
                    ],
                  ),
                )
              : RefreshIndicator(
                  onRefresh: _load,
                  child: ListView(
                    padding: const EdgeInsets.all(16),
                    children: [
                      Text(_student!.displayName, style: Theme.of(context).textTheme.headlineSmall),
                      Text('Admission: ${_student!.admissionNo}'),
                      Text('Status: ${_student!.status}'),
                      const SizedBox(height: 16),
                      Row(
                        children: [
                          Text('Enrollments', style: Theme.of(context).textTheme.titleMedium),
                          const Spacer(),
                          TextButton(onPressed: _addEnrollment, child: const Text('Add')),
                        ],
                      ),
                      if (_enrollments.isEmpty)
                        const Text('No enrollments')
                      else
                        ..._enrollments.map(
                          (e) => ListTile(
                            title: Text('${e.status} — class ${e.classId.substring(0, 8)}…'),
                            subtitle: Text('Section ${e.sectionId.substring(0, 8)}… • ${e.startsOn}'),
                            trailing: e.status == 'active'
                                ? PopupMenuButton<String>(
                                    onSelected: (v) {
                                      if (v == 'move') _moveEnrollment(e);
                                      if (v == 'close') _closeEnrollment(e);
                                    },
                                    itemBuilder: (_) => const [
                                      PopupMenuItem(value: 'move', child: Text('Move class/section')),
                                      PopupMenuItem(value: 'close', child: Text('Close enrollment')),
                                    ],
                                  )
                                : null,
                          ),
                        ),
                      const SizedBox(height: 16),
                      Text('Cards', style: Theme.of(context).textTheme.titleMedium),
                      if (_cardAssignments.isEmpty)
                        const Text('No card assignments')
                      else
                        ..._cardAssignments.map(
                          (a) => ListTile(
                            title: Text('Card ${a.physicalCardId.substring(0, 8)}…'),
                            subtitle: Text(a.status),
                          ),
                        ),
                      const SizedBox(height: 16),
                      Row(
                        children: [
                          Text('Guardians', style: Theme.of(context).textTheme.titleMedium),
                          const Spacer(),
                          TextButton(onPressed: _linkGuardian, child: const Text('Link')),
                        ],
                      ),
                      if (_guardianLinks.isEmpty)
                        const Text('No guardians linked')
                      else
                        ..._guardianLinks.map(
                          (g) => ListTile(
                            title: Text(g.relationshipType),
                            subtitle: Text(
                              'Guardian ${g.guardianId.substring(0, 8)}… • ${g.isPrimaryContact ? 'primary' : 'secondary'}',
                            ),
                          ),
                        ),
                    ],
                  ),
                ),
    );
  }
}
