import 'package:flutter/material.dart';

import '../academic/academic_models.dart';
import '../app/admin_dependencies.dart';
import '../operations/operations_models.dart';
import '../people/admin_people_api.dart';
import '../people/people_models.dart';
import 'admin_widgets.dart';
import 'format.dart';
import 'guardian_form_screen.dart';
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
  Map<String, GuardianDetail> _guardianById = const {};
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
      final resolved = <String, GuardianDetail>{};
      for (final link in _guardianLinks) {
        try {
          resolved[link.guardianId] = await widget.deps.peopleApi.fetchGuardian(link.guardianId);
        } catch (_) {}
      }
      _guardianById = resolved;
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
    final guardians = await widget.deps.peopleApi.fetchGuardians();
    if (years.isEmpty) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('No academic years configured.')));
      }
      return;
    }
    AcademicYearItem? year = years.first;
    SchoolClassItem? clazz;
    SectionItem? section;
    GuardianDetail? guardian;
    var linkGuardian = true;
    final relationshipCtrl = TextEditingController(text: 'parent');
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
                  DropdownButtonFormField<AcademicYearItem>(
                    initialValue: year,
                    decoration: const InputDecoration(labelText: 'Academic year'),
                    items: years
                        .map((y) => DropdownMenuItem(value: y, child: Text(y.name)))
                        .toList(),
                    onChanged: (v) => setLocal(() => year = v),
                  ),
                  FutureBuilder<List<SchoolClassItem>>(
                    future: widget.deps.academicApi.fetchClasses(),
                    builder: (context, snap) {
                      final classes = snap.data ?? const [];
                      return DropdownButtonFormField<SchoolClassItem>(
                        initialValue: clazz,
                        decoration: const InputDecoration(labelText: 'Class'),
                        items: classes
                            .map((c) => DropdownMenuItem(value: c, child: Text(c.name)))
                            .toList(),
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
                        return DropdownButtonFormField<SectionItem>(
                          initialValue: section,
                          decoration: const InputDecoration(labelText: 'Section'),
                          items: sections
                              .map((s) => DropdownMenuItem(value: s, child: Text(s.name)))
                              .toList(),
                          onChanged: (v) => setLocal(() => section = v),
                        );
                      },
                    ),
                  SwitchListTile(
                    contentPadding: EdgeInsets.zero,
                    title: const Text('Also link parent/guardian'),
                    value: linkGuardian,
                    onChanged: (v) => setLocal(() => linkGuardian = v),
                  ),
                  if (linkGuardian) ...[
                    DropdownButtonFormField<GuardianDetail>(
                      initialValue: guardian,
                      decoration: const InputDecoration(labelText: 'Guardian'),
                      items: guardians
                          .map(
                            (g) => DropdownMenuItem(
                              value: g,
                              child: Text(g.displayName),
                            ),
                          )
                          .toList(),
                      onChanged: (v) => setLocal(() => guardian = v),
                    ),
                    TextField(
                      controller: relationshipCtrl,
                      decoration: const InputDecoration(labelText: 'Relationship'),
                    ),
                  ],
                ],
              ),
            ),
            actions: [
              TextButton(onPressed: () => Navigator.pop(context), child: const Text('Cancel')),
              FilledButton(
                onPressed: () async {
                  if (year == null || clazz == null || section == null) return;
                  if (linkGuardian && guardian == null) return;
                  try {
                    await widget.deps.peopleApi.createEnrollment({
                      'student_id': widget.studentId,
                      'academic_year_id': year!.id,
                      'class_id': clazz!.id,
                      'section_id': section!.id,
                      'starts_on': DateTime.now().toIso8601String().split('T').first,
                    });
                    if (linkGuardian && guardian != null) {
                      await widget.deps.peopleApi.attachStudentGuardian(widget.studentId, {
                        'guardian_id': guardian!.id,
                        'relationship_type': relationshipCtrl.text.trim().isEmpty
                            ? 'parent'
                            : relationshipCtrl.text.trim(),
                        'is_primary_contact': true,
                      });
                    }
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
    relationshipCtrl.dispose();
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

  Future<void> _createParent() async {
    final created = await Navigator.of(context).push<bool>(
      MaterialPageRoute(builder: (_) => GuardianFormScreen(deps: widget.deps)),
    );
    if (created == true && mounted) {
      final guardians = await widget.deps.peopleApi.fetchGuardians();
      if (guardians.isEmpty) return;
      final newest = guardians.first;
      try {
        await widget.deps.peopleApi.attachStudentGuardian(widget.studentId, {
          'guardian_id': newest.id,
          'relationship_type': 'parent',
          'is_primary_contact': _guardianLinks.isEmpty,
        });
        _load();
      } on AdminPeopleApiFailure catch (e) {
        if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(e.message)));
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: Text(_student?.displayName ?? 'Student'),
        actions: [
          IconButton(onPressed: _load, icon: const Icon(Icons.refresh), tooltip: 'Refresh'),
          if (_student != null)
            IconButton(onPressed: _edit, icon: const Icon(Icons.edit), tooltip: 'Edit'),
        ],
      ),
      body: _loading
          ? const Center(child: CircularProgressIndicator())
          : _error != null
              ? ErrorRetry(message: _error!, onRetry: _load)
              : RefreshIndicator(
                  onRefresh: _load,
                  child: ListView(
                    padding: const EdgeInsets.all(16),
                    children: [
                      _StudentHeader(student: _student!),
                      const SizedBox(height: 20),
                      SectionHeader(
                        title: 'Enrollments',
                        action: TextButton.icon(
                          onPressed: _addEnrollment,
                          icon: const Icon(Icons.add),
                          label: const Text('Add'),
                        ),
                      ),
                      const SizedBox(height: 8),
                      if (_enrollments.isEmpty)
                        const EmptyState(
                          icon: Icons.class_outlined,
                          title: 'No enrollments yet',
                          subtitle: 'Enroll this student into a class and section.',
                        )
                      else
                        ..._enrollments.map(
                          (e) => Card(
                            margin: const EdgeInsets.only(bottom: 8),
                            child: ListTile(
                              title: Row(
                                children: [
                                  Expanded(child: Text('Started ${formatDateString(e.startsOn)}')),
                                  StatusChip(status: e.status),
                                ],
                              ),
                              subtitle: e.endsOn == null
                                  ? null
                                  : Text('Ended ${formatDateString(e.endsOn!)}'),
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
                        ),
                      const SizedBox(height: 20),
                      const SectionHeader(title: 'Cards'),
                      const SizedBox(height: 8),
                      if (_cardAssignments.isEmpty)
                        const EmptyState(
                          icon: Icons.credit_card_outlined,
                          title: 'No card assigned',
                          subtitle: 'Assign a physical ID card to enable gate and bus taps.',
                        )
                      else
                        ..._cardAssignments.map(
                          (a) {
                            final shortId = a.physicalCardId.length > 8
                                ? a.physicalCardId.substring(0, 8)
                                : a.physicalCardId;
                            return Card(
                              margin: const EdgeInsets.only(bottom: 8),
                              child: ListTile(
                                leading: const Icon(Icons.credit_card_outlined),
                                title: Text('Card $shortId'),
                                trailing: StatusChip(status: a.status),
                              ),
                            );
                          },
                        ),
                      const SizedBox(height: 20),
                      SectionHeader(
                        title: 'Guardians',
                        action: Row(
                          mainAxisSize: MainAxisSize.min,
                          children: [
                            TextButton(onPressed: _linkGuardian, child: const Text('Link existing')),
                            TextButton(onPressed: _createParent, child: const Text('New parent')),
                          ],
                        ),
                      ),
                      const SizedBox(height: 8),
                      if (_guardianLinks.isEmpty)
                        const EmptyState(
                          icon: Icons.family_restroom_outlined,
                          title: 'No guardians linked',
                          subtitle: 'Link a parent so they can use the Parent app.',
                        )
                      else
                        ..._guardianLinks.map(
                          (g) {
                            final parent = _guardianById[g.guardianId];
                            return Card(
                              margin: const EdgeInsets.only(bottom: 8),
                              child: ListTile(
                                leading: const Icon(Icons.person_outline),
                                title: Text(parent?.displayName ?? 'Parent'),
                                subtitle: Text(
                                  [
                                    prettifyLabel(g.relationshipType),
                                    if (parent?.email != null) parent!.email!,
                                    if (g.isPrimaryContact) 'Primary contact',
                                    if (parent?.userId != null) 'Parent app login linked',
                                    if (parent?.userId == null) 'No parent-app login yet',
                                  ].join(' · '),
                                ),
                              ),
                            );
                          },
                        ),
                    ],
                  ),
                ),
    );
  }
}

class _StudentHeader extends StatelessWidget {
  const _StudentHeader({required this.student});

  final StudentDetail student;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final scheme = theme.colorScheme;
    final initials = '${student.firstName.isNotEmpty ? student.firstName[0] : '?'}'
        '${student.lastName.isNotEmpty ? student.lastName[0] : ''}';
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Row(
          children: [
            CircleAvatar(
              radius: 28,
              backgroundColor: scheme.primaryContainer,
              child: Text(
                initials.toUpperCase(),
                style: theme.textTheme.titleLarge?.copyWith(
                  color: scheme.onPrimaryContainer,
                  fontWeight: FontWeight.w700,
                ),
              ),
            ),
            const SizedBox(width: 14),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    student.displayName,
                    style: theme.textTheme.headlineSmall?.copyWith(fontWeight: FontWeight.w700),
                  ),
                  const SizedBox(height: 2),
                  Text(
                    'Admission ${student.admissionNo}',
                    style: theme.textTheme.bodyMedium?.copyWith(
                      color: scheme.onSurfaceVariant,
                    ),
                  ),
                  if (student.dateOfBirth != null) ...[
                    const SizedBox(height: 2),
                    Text(
                      'Born ${formatDateString(student.dateOfBirth!)}',
                      style: theme.textTheme.bodyMedium?.copyWith(
                        color: scheme.onSurfaceVariant,
                      ),
                    ),
                  ],
                ],
              ),
            ),
            StatusChip(status: student.status),
          ],
        ),
      ),
    );
  }
}
