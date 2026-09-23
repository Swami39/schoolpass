import 'package:flutter/material.dart';

import '../academic/academic_models.dart';
import '../app/admin_app_controller.dart';
import '../app/admin_dependencies.dart';
import '../people/people_models.dart';
import '../school/school_profile_models.dart';
import 'academic_form_screens.dart';
import 'admin_widgets.dart';
import 'enroll_student_wizard.dart';
import 'imports_hub_screen.dart';
import 'school_profile_screen.dart';
import 'school_structure_screen.dart';
import 'staff_form_screen.dart';

/// Guided onboarding home: the five steps that get a school running,
/// each with live progress and a deep link into the right flow.
class SetupChecklistScreen extends StatefulWidget {
  const SetupChecklistScreen({required this.controller, required this.deps, super.key});

  final AdminAppController controller;
  final AdminDependencies deps;

  @override
  State<SetupChecklistScreen> createState() => _SetupChecklistScreenState();
}

class _SetupData {
  _SetupData({
    required this.profile,
    required this.classes,
    required this.sections,
    required this.teachers,
    required this.assignments,
    required this.students,
    required this.enrollments,
    required this.guardians,
  });

  final SchoolProfile? profile;
  final List<SchoolClassItem> classes;
  final List<SectionItem> sections;
  final List<StaffListItem> teachers;
  final List<TeacherAssignmentItem> assignments;
  final List<StudentDetail> students;
  final List<EnrollmentDetail> enrollments;
  final List<GuardianDetail> guardians;
}

class _SetupChecklistScreenState extends State<SetupChecklistScreen> {
  _SetupData? _data;
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
      final results = await Future.wait([
        // A school with no profile yet gets a 404 here; treat that as "not done".
        // The explicit <SchoolProfile?> keeps the null from catchError type-safe.
        widget.deps.schoolApi.fetchProfile().then<SchoolProfile?>((v) => v).catchError((_) => null),
        widget.deps.academicApi.fetchClasses(),
        widget.deps.academicApi.fetchSections(),
        widget.deps.peopleApi.fetchStaff(staffType: 'teacher', limit: 200),
        widget.deps.academicApi.fetchTeacherAssignments(),
        widget.deps.peopleApi.fetchStudents(status: 'active', limit: 200),
        widget.deps.peopleApi.fetchEnrollments(status: 'active', limit: 200),
        widget.deps.peopleApi.fetchGuardians(limit: 200),
      ]);
      if (!mounted) return;
      setState(() {
        _data = _SetupData(
          profile: results[0] as SchoolProfile?,
          classes: results[1] as List<SchoolClassItem>,
          sections: results[2] as List<SectionItem>,
          teachers: results[3] as List<StaffListItem>,
          assignments: results[4] as List<TeacherAssignmentItem>,
          students: results[5] as List<StudentDetail>,
          enrollments: results[6] as List<EnrollmentDetail>,
          guardians: results[7] as List<GuardianDetail>,
        );
        _loading = false;
      });
    } catch (_) {
      if (!mounted) return;
      setState(() {
        _loading = false;
        _error = 'Could not load setup progress. Check your connection and retry.';
      });
    }
  }

  Future<void> _go(Widget screen) async {
    await Navigator.of(context).push(MaterialPageRoute(builder: (_) => screen));
    if (mounted) _load();
  }

  @override
  Widget build(BuildContext context) {
    if (_loading) return const Center(child: CircularProgressIndicator());
    if (_error != null) return ErrorRetry(message: _error!, onRetry: _load);
    final data = _data!;

    final profileDone =
        data.profile != null && data.profile!.legalName.trim().isNotEmpty;
    final structureDone = data.sections.isNotEmpty;
    final teachersDone = data.assignments.isNotEmpty;
    final studentsDone = data.enrollments.isNotEmpty;
    final parentsDone = data.guardians.isNotEmpty;
    final doneCount = [
      profileDone,
      structureDone,
      teachersDone,
      studentsDone,
      parentsDone,
    ].where((d) => d).length;

    final theme = Theme.of(context);
    return RefreshIndicator(
      onRefresh: _load,
      child: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          Text('Get your school ready', style: theme.textTheme.headlineSmall),
          const SizedBox(height: 4),
          Text(
            'Follow the steps in order — each one builds on the last.',
            style: theme.textTheme.bodyMedium?.copyWith(
              color: theme.colorScheme.onSurfaceVariant,
            ),
          ),
          const SizedBox(height: 12),
          _ProgressHeader(done: doneCount, total: 5),
          const SizedBox(height: 20),
          _StepCard(
            step: 1,
            done: profileDone,
            icon: Icons.home_work_outlined,
            title: 'Set up the school',
            subtitle: profileDone
                ? data.profile!.displayName?.trim().isNotEmpty == true
                      ? data.profile!.displayName!
                      : data.profile!.legalName
                : 'Add the school name, timezone, and contact details',
            cta: profileDone ? 'Review' : 'Start',
            onTap: () => _go(SchoolProfileScreen(controller: widget.controller)),
          ),
          _StepCard(
            step: 2,
            done: structureDone,
            icon: Icons.account_tree_outlined,
            title: 'Add classes & sections',
            subtitle: structureDone
                ? '${data.classes.length} classes · ${data.sections.length} sections'
                : 'Create classes, then a section (like A, B, C) under each',
            cta: structureDone ? 'Manage' : 'Start',
            onTap: () => _go(SchoolStructureScreen(deps: widget.deps)),
          ),
          _StepCard(
            step: 3,
            done: teachersDone,
            icon: Icons.badge_outlined,
            title: 'Add teachers & assign them',
            subtitle: data.teachers.isEmpty
                ? 'Add your teaching staff first'
                : '${data.teachers.length} teachers · ${data.assignments.length} section assignments',
            cta: data.teachers.isEmpty ? 'Add teacher' : 'Assign',
            onTap: () => _go(
              data.teachers.isEmpty
                  ? StaffFormScreen(deps: widget.deps)
                  : TeacherAssignmentFormScreen(deps: widget.deps),
            ),
          ),
          _StepCard(
            step: 4,
            done: studentsDone,
            icon: Icons.school_outlined,
            title: 'Enroll students',
            subtitle: studentsDone
                ? '${data.students.length} students · ${data.enrollments.length} enrollments'
                : 'Add children straight into their class section',
            cta: studentsDone ? 'Enroll more' : 'Start',
            onTap: () => _go(EnrollStudentWizard(deps: widget.deps)),
          ),
          _StepCard(
            step: 5,
            done: parentsDone,
            icon: Icons.family_restroom_outlined,
            title: 'Link parents to children',
            subtitle: parentsDone
                ? '${data.guardians.length} parents linked — add more from any section'
                : 'Create parent logins and attach each child',
            cta: parentsDone ? 'Manage' : 'Start',
            onTap: () => _go(SchoolStructureScreen(deps: widget.deps)),
          ),
          const SizedBox(height: 20),
          const SectionHeader(title: 'Other ways to set up'),
          const SizedBox(height: 8),
          AdminSectionCard(
            icon: Icons.upload_file_outlined,
            title: 'Bulk import school data',
            subtitle: 'One CSV for classes, teachers, students, and parent links',
            onTap: () => _go(ImportsHubScreen(deps: widget.deps)),
          ),
        ],
      ),
    );
  }
}

class _ProgressHeader extends StatelessWidget {
  const _ProgressHeader({required this.done, required this.total});

  final int done;
  final int total;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final scheme = theme.colorScheme;
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: scheme.primaryContainer,
        borderRadius: BorderRadius.circular(16),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Expanded(
                child: Text(
                  done == total ? 'All set — school is ready' : '$done of $total steps complete',
                  style: theme.textTheme.titleMedium?.copyWith(
                    color: scheme.onPrimaryContainer,
                    fontWeight: FontWeight.w700,
                  ),
                ),
              ),
              Text(
                '${((done / total) * 100).round()}%',
                style: theme.textTheme.titleMedium?.copyWith(
                  color: scheme.onPrimaryContainer,
                  fontWeight: FontWeight.w800,
                ),
              ),
            ],
          ),
          const SizedBox(height: 10),
          ClipRRect(
            borderRadius: BorderRadius.circular(999),
            child: LinearProgressIndicator(
              value: done / total,
              minHeight: 8,
              backgroundColor: scheme.onPrimaryContainer.withValues(alpha: 0.18),
              valueColor: AlwaysStoppedAnimation<Color>(scheme.primary),
            ),
          ),
        ],
      ),
    );
  }
}

class _StepCard extends StatelessWidget {
  const _StepCard({
    required this.step,
    required this.done,
    required this.icon,
    required this.title,
    required this.subtitle,
    required this.cta,
    required this.onTap,
  });

  final int step;
  final bool done;
  final IconData icon;
  final String title;
  final String subtitle;
  final String cta;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final scheme = theme.colorScheme;
    return Padding(
      padding: const EdgeInsets.only(bottom: 12),
      child: Card(
        child: InkWell(
          borderRadius: BorderRadius.circular(16),
          onTap: onTap,
          child: Padding(
            padding: const EdgeInsets.all(16),
            child: Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                _StepBadge(step: step, done: done),
                const SizedBox(width: 14),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Row(
                        children: [
                          Icon(icon, size: 18, color: scheme.primary),
                          const SizedBox(width: 6),
                          Expanded(
                            child: Text(
                              title,
                              style: theme.textTheme.titleMedium?.copyWith(
                                fontWeight: FontWeight.w700,
                              ),
                            ),
                          ),
                        ],
                      ),
                      const SizedBox(height: 4),
                      Text(
                        subtitle,
                        style: theme.textTheme.bodyMedium?.copyWith(
                          color: scheme.onSurfaceVariant,
                        ),
                      ),
                      const SizedBox(height: 10),
                      Align(
                        alignment: Alignment.centerLeft,
                        child: FilledButton.tonal(
                          onPressed: onTap,
                          child: Text(cta),
                        ),
                      ),
                    ],
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

class _StepBadge extends StatelessWidget {
  const _StepBadge({required this.step, required this.done});

  final int step;
  final bool done;

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    return Container(
      width: 36,
      height: 36,
      decoration: BoxDecoration(
        shape: BoxShape.circle,
        color: done ? const Color(0xFFDCFCE7) : scheme.secondaryContainer,
      ),
      child: Center(
        child: done
            ? const Icon(Icons.check, size: 20, color: Color(0xFF166534))
            : Text(
                '$step',
                style: TextStyle(
                  color: scheme.onSecondaryContainer,
                  fontWeight: FontWeight.w800,
                  fontSize: 16,
                ),
              ),
      ),
    );
  }
}
