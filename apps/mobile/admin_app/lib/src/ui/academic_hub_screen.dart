import 'package:flutter/material.dart';

import '../academic/academic_models.dart';
import '../app/admin_dependencies.dart';
import 'academic_list_screen.dart';

class AcademicHubScreen extends StatelessWidget {
  const AcademicHubScreen({required this.deps, super.key});

  final AdminDependencies deps;

  @override
  Widget build(BuildContext context) {
    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        ListTile(
          leading: const Icon(Icons.calendar_month),
          title: const Text('Academic years'),
          onTap: () => Navigator.of(context).push(
            MaterialPageRoute(
              builder: (_) => AcademicListScreen<AcademicYearItem>(
                title: 'Academic years',
                deps: deps,
                loader: deps.academicApi.fetchAcademicYears,
                label: (item) => '${item.name} (${item.code}) — ${item.status}',
              ),
            ),
          ),
        ),
        ListTile(
          leading: const Icon(Icons.class_),
          title: const Text('Classes & sections'),
          onTap: () => Navigator.of(context).push(
            MaterialPageRoute(
              builder: (_) => AcademicListScreen<SchoolClassItem>(
                title: 'Classes',
                deps: deps,
                loader: deps.academicApi.fetchClasses,
                label: (item) => '${item.name} (${item.code}) — ${item.status}',
              ),
            ),
          ),
        ),
        ListTile(
          leading: const Icon(Icons.menu_book),
          title: const Text('Subjects'),
          onTap: () => Navigator.of(context).push(
            MaterialPageRoute(
              builder: (_) => AcademicListScreen<SubjectItem>(
                title: 'Subjects',
                deps: deps,
                loader: deps.academicApi.fetchSubjects,
                label: (item) => '${item.name} (${item.code}) — ${item.status}',
              ),
            ),
          ),
        ),
        ListTile(
          leading: const Icon(Icons.person_pin),
          title: const Text('Teacher assignments'),
          onTap: () => Navigator.of(context).push(
            MaterialPageRoute(
              builder: (_) => AcademicListScreen<TeacherAssignmentItem>(
                title: 'Teacher assignments',
                deps: deps,
                loader: deps.academicApi.fetchTeacherAssignments,
                label: (item) => '${item.assignmentRole} — section ${item.sectionId.substring(0, 8)}…',
              ),
            ),
          ),
        ),
      ],
    );
  }
}
