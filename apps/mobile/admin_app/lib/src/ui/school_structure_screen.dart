import 'package:flutter/material.dart';
import 'package:schoolpass_design/schoolpass_design.dart';

import '../academic/academic_models.dart';
import '../app/admin_dependencies.dart';
import '../people/people_models.dart';
import 'academic_form_screens.dart';
import 'admin_widgets.dart';
import 'section_detail_screen.dart';

/// The school's academic structure: pick a year, open a class,
/// and manage its sections — students, teachers, and parents
/// all live one tap away inside each section.
class SchoolStructureScreen extends StatefulWidget {
  const SchoolStructureScreen({required this.deps, super.key});

  final AdminDependencies deps;

  @override
  State<SchoolStructureScreen> createState() => _SchoolStructureScreenState();
}

class _SchoolStructureScreenState extends State<SchoolStructureScreen> {
  List<AcademicYearItem> _years = const [];
  List<SchoolClassItem> _classes = const [];
  List<SectionItem> _sections = const [];
  List<EnrollmentDetail> _enrollments = const [];
  List<TeacherAssignmentItem> _assignments = const [];

  AcademicYearItem? _year;
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
        widget.deps.academicApi.fetchAcademicYears(),
        widget.deps.academicApi.fetchClasses(),
        widget.deps.academicApi.fetchSections(),
        widget.deps.peopleApi.fetchEnrollments(status: 'active', limit: 200),
        widget.deps.academicApi.fetchTeacherAssignments(),
      ]);
      if (!mounted) return;
      final years = results[0] as List<AcademicYearItem>;
      setState(() {
        _years = years;
        _classes = results[1] as List<SchoolClassItem>;
        _sections = results[2] as List<SectionItem>;
        _enrollments = results[3] as List<EnrollmentDetail>;
        _assignments = results[4] as List<TeacherAssignmentItem>;
        _year = _pickYear(years, _year?.id);
        _loading = false;
      });
    } catch (_) {
      if (!mounted) return;
      setState(() {
        _loading = false;
        _error = 'Could not load the school structure.';
      });
    }
  }

  AcademicYearItem? _pickYear(List<AcademicYearItem> years, String? keepId) {
    if (years.isEmpty) return null;
    if (keepId != null) {
      for (final y in years) {
        if (y.id == keepId) return y;
      }
    }
    for (final y in years) {
      if (y.status.toLowerCase() == 'active') return y;
    }
    return years.first;
  }

  Future<void> _openForm(Widget screen) async {
    await Navigator.of(context).push(MaterialPageRoute(builder: (_) => screen));
    if (mounted) _load();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Classes & sections'),
        actions: [
          IconButton(
            tooltip: 'Add class',
            icon: const Icon(Icons.add),
            onPressed: () => _openForm(SchoolClassFormScreen(deps: widget.deps)),
          ),
        ],
      ),
      body: _loading
          ? const Center(child: CircularProgressIndicator())
          : _error != null
              ? ErrorRetry(message: _error!, onRetry: _load)
              : _buildBody(),
    );
  }

  Widget _buildBody() {
    final theme = Theme.of(context);
    if (_years.isEmpty) {
      return Center(
        child: EmptyState(
          icon: Icons.calendar_month_outlined,
          title: 'No academic year yet',
          subtitle: 'Create an academic year before adding classes.',
          actionLabel: 'Add academic year',
          onAction: () => _openForm(AcademicYearFormScreen(deps: widget.deps)),
        ),
      );
    }
    if (_classes.isEmpty) {
      return Center(
        child: EmptyState(
          icon: Icons.class_outlined,
          title: 'No classes yet',
          subtitle: 'Add your first class — you can create its first section at the same time.',
          actionLabel: 'Add class',
          onAction: () => _openForm(SchoolClassFormScreen(deps: widget.deps)),
        ),
      );
    }

    final yearId = _year?.id;
    final sectionsByClass = <String, List<SectionItem>>{};
    for (final s in _sections) {
      sectionsByClass.putIfAbsent(s.classId, () => []).add(s);
    }
    final enrollmentsBySection = <String, int>{};
    for (final e in _enrollments) {
      if (yearId != null && e.academicYearId != yearId) continue;
      enrollmentsBySection[e.sectionId] = (enrollmentsBySection[e.sectionId] ?? 0) + 1;
    }
    final assignmentsBySection = <String, int>{};
    for (final a in _assignments) {
      assignmentsBySection[a.sectionId] = (assignmentsBySection[a.sectionId] ?? 0) + 1;
    }

    return RefreshIndicator(
      onRefresh: _load,
      child: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          DropdownButtonFormField<AcademicYearItem>(
            initialValue: _year,
            items: _years
                .map((y) => DropdownMenuItem(value: y, child: Text(y.name)))
                .toList(),
            onChanged: (v) => setState(() => _year = v),
            decoration: const InputDecoration(
              labelText: 'Academic year',
              prefixIcon: Icon(Icons.calendar_month_outlined),
            ),
          ),
          const SizedBox(height: 8),
          Text(
            'Open a class to see its sections. Open a section to manage its students, teachers, and parents.',
            style: theme.textTheme.bodySmall?.copyWith(
              color: theme.colorScheme.onSurfaceVariant,
            ),
          ),
          const SizedBox(height: 12),
          SectionLabel(
            'Classes',
            trailing: Text(
              '${_classes.length}',
              style: DesignTypography.mono(size: 12, color: DesignColors.ink3),
            ),
          ),
          for (final clazz in _classes) ...[
            _ClassTile(
              clazz: clazz,
              sections: sectionsByClass[clazz.id] ?? const [],
              enrollmentsBySection: enrollmentsBySection,
              assignmentsBySection: assignmentsBySection,
              onAddSection: () => _openForm(
                SectionFormScreen(deps: widget.deps, initialClassId: clazz.id),
              ),
              onOpenSection: (section) async {
                await Navigator.of(context).push(
                  MaterialPageRoute(
                    builder: (_) => SectionDetailScreen(
                      deps: widget.deps,
                      classItem: clazz,
                      section: section,
                    ),
                  ),
                );
                if (mounted) _load();
              },
            ),
            const SizedBox(height: 8),
          ],
          const SizedBox(height: 8),
          OutlinedButton.icon(
            onPressed: () => _openForm(SectionFormScreen(deps: widget.deps)),
            icon: const Icon(Icons.add),
            label: const Text('Add section'),
          ),
        ],
      ),
    );
  }
}

class _ClassTile extends StatelessWidget {
  const _ClassTile({
    required this.clazz,
    required this.sections,
    required this.enrollmentsBySection,
    required this.assignmentsBySection,
    required this.onAddSection,
    required this.onOpenSection,
  });

  final SchoolClassItem clazz;
  final List<SectionItem> sections;
  final Map<String, int> enrollmentsBySection;
  final Map<String, int> assignmentsBySection;
  final VoidCallback onAddSection;
  final ValueChanged<SectionItem> onOpenSection;

  @override
  Widget build(BuildContext context) {
    final totalStudents = sections.fold<int>(
      0,
      (sum, s) => sum + (enrollmentsBySection[s.id] ?? 0),
    );
    return Panel(
      padding: EdgeInsets.zero,
      child: ExpansionTile(
        tilePadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 4),
        leading: Container(
          width: 44,
          height: 44,
          decoration: BoxDecoration(
            color: DesignColors.brandSoft,
            borderRadius: BorderRadius.circular(12),
          ),
          child: const Icon(Icons.class_outlined, color: DesignColors.brandInk),
        ),
        title: Row(
          children: [
            Expanded(
              child: Text(
                clazz.name,
                style: const TextStyle(
                  fontWeight: FontWeight.w700,
                  fontSize: 15,
                  color: DesignColors.ink,
                ),
              ),
            ),
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
              decoration: BoxDecoration(
                color: DesignColors.brandSoft,
                borderRadius: BorderRadius.circular(999),
              ),
              child: Text(
                '${sections.length} ${sections.length == 1 ? 'section' : 'sections'}',
                style: const TextStyle(
                  color: DesignColors.brandInk,
                  fontWeight: FontWeight.w700,
                  fontSize: 12,
                ),
              ),
            ),
          ],
        ),
        subtitle: Text(
          '${clazz.code}${totalStudents > 0 ? ' · $totalStudents students' : ''}',
          style: const TextStyle(fontSize: 12.5, color: DesignColors.ink2),
        ),
        children: [
          for (final section in sections)
            Padding(
              padding: const EdgeInsets.fromLTRB(16, 0, 16, 8),
              child: Panel(
                padding: const EdgeInsets.all(12),
                onTap: () => onOpenSection(section),
                child: Row(
                  children: [
                    InitialsAvatar(
                      initials: section.name.isEmpty
                          ? '?'
                          : section.name[0].toUpperCase(),
                      color: DesignColors.bus,
                      size: 40,
                    ),
                    const SizedBox(width: 12),
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(
                            'Section ${section.name}',
                            style: const TextStyle(
                              fontWeight: FontWeight.w700,
                              fontSize: 14,
                              color: DesignColors.ink,
                            ),
                          ),
                          const SizedBox(height: 2),
                          Text(
                            '${enrollmentsBySection[section.id] ?? 0} students · '
                            '${assignmentsBySection[section.id] ?? 0} teachers',
                            style: const TextStyle(
                              fontSize: 12,
                              color: DesignColors.ink2,
                            ),
                          ),
                        ],
                      ),
                    ),
                    StatusChip(status: section.status),
                    const SizedBox(width: 4),
                    const Icon(
                      Icons.chevron_right,
                      color: DesignColors.ink3,
                    ),
                  ],
                ),
              ),
            ),
          Padding(
            padding: const EdgeInsets.fromLTRB(16, 4, 16, 12),
            child: Align(
              alignment: Alignment.centerLeft,
              child: TextButton.icon(
                onPressed: onAddSection,
                icon: const Icon(Icons.add, size: 18),
                label: const Text('Add section'),
              ),
            ),
          ),
        ],
      ),
    );
  }
}
