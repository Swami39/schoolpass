import 'package:flutter/material.dart';
import 'package:schoolpass_design/schoolpass_design.dart';

import '../academic/academic_models.dart';
import '../app/admin_dependencies.dart';
import '../people/people_models.dart';
import 'academic_form_screens.dart';
import 'admin_widgets.dart';
import 'enroll_student_wizard.dart';
import 'link_guardian_screen.dart';
import 'student_detail_screen.dart';

/// Everything about one section in one place: its students (with their
/// parent links) and its teachers. This is where day-to-day setup happens.
class SectionDetailScreen extends StatefulWidget {
  const SectionDetailScreen({
    required this.deps,
    required this.classItem,
    required this.section,
    super.key,
  });

  final AdminDependencies deps;
  final SchoolClassItem classItem;
  final SectionItem section;

  @override
  State<SectionDetailScreen> createState() => _SectionDetailScreenState();
}

class _SectionDetailScreenState extends State<SectionDetailScreen> {
  List<EnrollmentDetail> _enrollments = const [];
  Map<String, StudentDetail> _students = const {};
  Map<String, List<StudentGuardianLink>> _linksByStudent = const {};
  Map<String, GuardianDetail> _guardians = const {};
  List<TeacherAssignmentItem> _assignments = const [];
  Map<String, StaffListItem> _staffByUserId = const {};

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
      final sectionId = widget.section.id;
      final results = await Future.wait([
        widget.deps.peopleApi.fetchEnrollments(sectionId: sectionId, status: 'active', limit: 200),
        widget.deps.peopleApi.fetchStudents(status: 'active', limit: 200),
        widget.deps.peopleApi.fetchGuardians(limit: 200),
        widget.deps.academicApi.fetchTeacherAssignments(sectionId: sectionId),
        widget.deps.peopleApi.fetchStaff(staffType: 'teacher', limit: 200),
      ]);
      final enrollments = results[0] as List<EnrollmentDetail>;
      final students = results[1] as List<StudentDetail>;
      final guardians = results[2] as List<GuardianDetail>;
      final assignments = results[3] as List<TeacherAssignmentItem>;
      final staff = results[4] as List<StaffListItem>;

      // Parent links for just this section's students (bounded fan-out).
      final studentIds = enrollments.map((e) => e.studentId).where((id) => id.isNotEmpty).toSet();
      final linksByStudent = <String, List<StudentGuardianLink>>{};
      await Future.wait(studentIds.map((id) async {
        try {
          linksByStudent[id] = await widget.deps.peopleApi.fetchStudentGuardians(id);
        } catch (_) {
          linksByStudent[id] = const [];
        }
      }));

      if (!mounted) return;
      setState(() {
        _enrollments = enrollments;
        _students = {for (final s in students) s.id: s};
        _linksByStudent = linksByStudent;
        _guardians = {for (final g in guardians) g.id: g};
        _assignments = assignments;
        _staffByUserId = {
          for (final s in staff)
            if (s.userId != null) s.userId!: s,
        };
        _loading = false;
      });
    } catch (_) {
      if (!mounted) return;
      setState(() {
        _loading = false;
        _error = 'Could not load this section.';
      });
    }
  }

  Future<void> _refresh() => _load();

  Future<void> _enrollStudent() async {
    await Navigator.of(context).push(
      MaterialPageRoute(
        builder: (_) => EnrollStudentWizard(
          deps: widget.deps,
          initialClassId: widget.classItem.id,
          initialSectionId: widget.section.id,
        ),
      ),
    );
    if (mounted) _load();
  }

  Future<void> _assignTeacher() async {
    await Navigator.of(context).push(
      MaterialPageRoute(
        builder: (_) => TeacherAssignmentFormScreen(
          deps: widget.deps,
          initialClassId: widget.classItem.id,
          initialSectionId: widget.section.id,
        ),
      ),
    );
    if (mounted) _load();
  }

  Future<void> _linkParent(StudentDetail student) async {
    final changed = await Navigator.of(context).push<bool>(
      MaterialPageRoute(
        builder: (_) => LinkGuardianScreen(
          deps: widget.deps,
          studentId: student.id,
          studentName: student.displayName,
        ),
      ),
    );
    if (changed == true && mounted) _load();
  }

  @override
  Widget build(BuildContext context) {
    return DefaultTabController(
      length: 2,
      child: Scaffold(
        appBar: AppBar(
          title: Text('${widget.classItem.name} · ${widget.section.name}'),
          bottom: const TabBar(
            tabs: [
              Tab(text: 'Students'),
              Tab(text: 'Teachers'),
            ],
          ),
        ),
        body: _loading
            ? const Center(child: CircularProgressIndicator())
            : _error != null
                ? ErrorRetry(message: _error!, onRetry: _load)
                : RefreshIndicator(
                    onRefresh: _refresh,
                    child: TabBarView(
                      children: [
                        _StudentsTab(
                          enrollments: _enrollments,
                          students: _students,
                          linksByStudent: _linksByStudent,
                          guardians: _guardians,
                          onEnroll: _enrollStudent,
                          onLinkParent: _linkParent,
                          onOpenStudent: (s) => Navigator.of(context).push(
                            MaterialPageRoute(
                              builder: (_) => StudentDetailScreen(
                                deps: widget.deps,
                                studentId: s.id,
                              ),
                            ),
                          ),
                        ),
                        _TeachersTab(
                          assignments: _assignments,
                          staffByUserId: _staffByUserId,
                          onAssign: _assignTeacher,
                        ),
                      ],
                    ),
                  ),
      ),
    );
  }
}

class _StudentsTab extends StatelessWidget {
  const _StudentsTab({
    required this.enrollments,
    required this.students,
    required this.linksByStudent,
    required this.guardians,
    required this.onEnroll,
    required this.onLinkParent,
    required this.onOpenStudent,
  });

  final List<EnrollmentDetail> enrollments;
  final Map<String, StudentDetail> students;
  final Map<String, List<StudentGuardianLink>> linksByStudent;
  final Map<String, GuardianDetail> guardians;
  final VoidCallback onEnroll;
  final ValueChanged<StudentDetail> onLinkParent;
  final ValueChanged<StudentDetail> onOpenStudent;

  @override
  Widget build(BuildContext context) {
    final rows = enrollments
        .map((e) => students[e.studentId])
        .whereType<StudentDetail>()
        .toList(growable: false);
    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        Row(
          children: [
            Expanded(
              child: Text(
                '${rows.length} ${rows.length == 1 ? 'student' : 'students'} enrolled',
                style: const TextStyle(
                  fontWeight: FontWeight.w700,
                  fontSize: 15,
                  color: DesignColors.ink,
                ),
              ),
            ),
            FilledButton.icon(
              onPressed: onEnroll,
              icon: const Icon(Icons.person_add_alt_outlined, size: 18),
              label: const Text('Enroll student'),
            ),
          ],
        ),
        const SizedBox(height: 12),
        if (rows.isEmpty)
          EmptyState(
            icon: Icons.school_outlined,
            title: 'No students yet',
            subtitle: 'Enroll the first child into this section.',
            actionLabel: 'Enroll student',
            onAction: onEnroll,
          )
        else
          for (final student in rows)
            _StudentRow(
              student: student,
              links: linksByStudent[student.id] ?? const [],
              guardians: guardians,
              onTap: () => onOpenStudent(student),
              onLinkParent: () => onLinkParent(student),
            ),
      ],
    );
  }
}

class _StudentRow extends StatelessWidget {
  const _StudentRow({
    required this.student,
    required this.links,
    required this.guardians,
    required this.onTap,
    required this.onLinkParent,
  });

  final StudentDetail student;
  final List<StudentGuardianLink> links;
  final Map<String, GuardianDetail> guardians;
  final VoidCallback onTap;
  final VoidCallback onLinkParent;

  @override
  Widget build(BuildContext context) {
    final activeLinks = links.where((l) => l.status.toLowerCase() == 'active').toList();
    final names = activeLinks
        .map((l) => guardians[l.guardianId]?.displayName)
        .whereType<String>()
        .toList();
    return Padding(
      padding: const EdgeInsets.only(bottom: 8),
      child: Panel(
        padding: const EdgeInsets.all(14),
        onTap: onTap,
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                InitialsAvatar(
                  initials: student.firstName.isEmpty
                      ? '?'
                      : student.firstName[0].toUpperCase(),
                  color: DesignColors.brand,
                  size: 44,
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        student.displayName,
                        style: const TextStyle(
                          fontWeight: FontWeight.w700,
                          fontSize: 15,
                          color: DesignColors.ink,
                        ),
                      ),
                      const SizedBox(height: 2),
                      Text(
                        'Admission ${student.admissionNo}',
                        style: const TextStyle(
                          fontSize: 12,
                          color: DesignColors.ink2,
                        ),
                      ),
                    ],
                  ),
                ),
                const Icon(Icons.chevron_right, color: DesignColors.ink3),
              ],
            ),
            const SizedBox(height: 10),
            if (names.isEmpty)
              GestureDetector(
                onTap: onLinkParent,
                child: const StatusPill(
                  kind: StatusKind.late,
                  label: 'No parent linked',
                ),
              )
            else
              Wrap(
                spacing: 6,
                runSpacing: 4,
                children: [
                  for (final name in names)
                    StatusPill(kind: StatusKind.present, label: name),
                  GestureDetector(
                    onTap: onLinkParent,
                    child: const StatusPill(
                      kind: StatusKind.neutral,
                      label: '+ Add',
                    ),
                  ),
                ],
              ),
          ],
        ),
      ),
    );
  }
}

class _TeachersTab extends StatelessWidget {
  const _TeachersTab({
    required this.assignments,
    required this.staffByUserId,
    required this.onAssign,
  });

  final List<TeacherAssignmentItem> assignments;
  final Map<String, StaffListItem> staffByUserId;
  final VoidCallback onAssign;

  @override
  Widget build(BuildContext context) {
    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        Row(
          children: [
            Expanded(
              child: Text(
                '${assignments.length} ${assignments.length == 1 ? 'teacher' : 'teachers'} assigned',
                style: const TextStyle(
                  fontWeight: FontWeight.w700,
                  fontSize: 15,
                  color: DesignColors.ink,
                ),
              ),
            ),
            FilledButton.icon(
              onPressed: onAssign,
              icon: const Icon(Icons.person_add_alt_outlined, size: 18),
              label: const Text('Assign teacher'),
            ),
          ],
        ),
        const SizedBox(height: 12),
        if (assignments.isEmpty)
          EmptyState(
            icon: Icons.badge_outlined,
            title: 'No teachers assigned',
            subtitle: 'Assign a class teacher or subject teacher to this section.',
            actionLabel: 'Assign teacher',
            onAction: onAssign,
          )
        else
          for (final a in assignments)
            Padding(
              padding: const EdgeInsets.only(bottom: 8),
              child: Panel(
                padding: const EdgeInsets.all(14),
                child: Row(
                  children: [
                    InitialsAvatar(
                      initials: _teacherInitial(a),
                      color: DesignColors.bus,
                      size: 44,
                    ),
                    const SizedBox(width: 12),
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(
                            staffByUserId[a.teacherUserId]?.email ??
                                staffByUserId[a.teacherUserId]?.employeeCode ??
                                'Teacher',
                            style: const TextStyle(
                              fontWeight: FontWeight.w700,
                              fontSize: 14,
                              color: DesignColors.ink,
                            ),
                          ),
                          if (staffByUserId[a.teacherUserId]?.employeeCode != null) ...[
                            const SizedBox(height: 2),
                            Text(
                              'ID ${staffByUserId[a.teacherUserId]!.employeeCode}',
                              style: const TextStyle(
                                fontSize: 12,
                                color: DesignColors.ink2,
                              ),
                            ),
                          ],
                        ],
                      ),
                    ),
                    StatusChip(status: a.assignmentRole),
                  ],
                ),
              ),
            ),
      ],
    );
  }

  String _teacherInitial(TeacherAssignmentItem a) {
    final staff = staffByUserId[a.teacherUserId];
    final source = staff?.email ?? staff?.employeeCode ?? '';
    if (source.isEmpty) return 'T';
    return source[0].toUpperCase();
  }
}
