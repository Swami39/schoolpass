import 'package:flutter/material.dart';
import 'package:schoolpass_design/schoolpass_design.dart';

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
    // First incomplete step is the "current" one.
    final currentStep = [
      profileDone,
      structureDone,
      teachersDone,
      studentsDone,
      parentsDone,
    ].indexWhere((d) => !d);

    return RefreshIndicator(
      onRefresh: _load,
      child: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          HeroCard(
            eyebrow: 'Setup checklist',
            title: doneCount == 5 ? 'All set — school is ready' : 'Get started',
            subtitle:
                '$doneCount of 5 steps complete · ${((doneCount / 5) * 100).round()}%',
          ),
          const SizedBox(height: 20),
          const SectionLabel('Steps in order'),
          _StepCard(
            step: 1,
            done: profileDone,
            isCurrent: currentStep == 0,
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
            isCurrent: currentStep == 1,
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
            isCurrent: currentStep == 2,
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
            isCurrent: currentStep == 3,
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
            isCurrent: currentStep == 4,
            icon: Icons.family_restroom_outlined,
            title: 'Link parents to children',
            subtitle: parentsDone
                ? '${data.guardians.length} parents linked — add more from any section'
                : 'Create parent logins and attach each child',
            cta: parentsDone ? 'Manage' : 'Start',
            onTap: () => _go(SchoolStructureScreen(deps: widget.deps)),
          ),
          const SizedBox(height: 20),
          const SectionLabel('Other ways to set up'),
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

class _StepCard extends StatelessWidget {
  const _StepCard({
    required this.step,
    required this.done,
    required this.isCurrent,
    required this.icon,
    required this.title,
    required this.subtitle,
    required this.cta,
    required this.onTap,
  });

  final int step;
  final bool done;
  final bool isCurrent;
  final IconData icon;
  final String title;
  final String subtitle;
  final String cta;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 12),
      child: Panel(
        onTap: onTap,
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            _StepNode(step: step, done: done, isCurrent: isCurrent),
            const SizedBox(width: 14),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    children: [
                      Icon(icon, size: 18, color: DesignColors.brandInk),
                      const SizedBox(width: 6),
                      Expanded(
                        child: Text(
                          title,
                          style: const TextStyle(
                            fontWeight: FontWeight.w700,
                            fontSize: 15,
                            color: DesignColors.ink,
                          ),
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: 4),
                  Text(
                    subtitle,
                    style: const TextStyle(
                      fontSize: 13,
                      color: DesignColors.ink2,
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
    );
  }
}

class _StepNode extends StatelessWidget {
  const _StepNode({
    required this.step,
    required this.done,
    required this.isCurrent,
  });

  final int step;
  final bool done;
  final bool isCurrent;

  @override
  Widget build(BuildContext context) {
    final status = context.status;
    final Color bg;
    final Widget inner;
    if (done) {
      bg = status.softOf(StatusKind.present);
      inner = Icon(Icons.check, size: 20, color: status.of(StatusKind.present));
    } else if (isCurrent) {
      bg = DesignColors.brand;
      inner = Text(
        '$step',
        style: const TextStyle(
          color: Colors.white,
          fontWeight: FontWeight.w800,
          fontSize: 16,
        ),
      );
    } else {
      bg = status.softOf(StatusKind.neutral);
      inner = Text(
        '$step',
        style: TextStyle(
          color: status.of(StatusKind.neutral),
          fontWeight: FontWeight.w800,
          fontSize: 16,
        ),
      );
    }
    return Container(
      width: 36,
      height: 36,
      decoration: BoxDecoration(shape: BoxShape.circle, color: bg),
      child: Center(child: inner),
    );
  }
}
