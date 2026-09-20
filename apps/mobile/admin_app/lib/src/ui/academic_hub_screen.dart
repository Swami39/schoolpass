import 'package:flutter/material.dart';

import '../academic/academic_models.dart';
import '../app/admin_dependencies.dart';
import 'academic_form_screens.dart';
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
          subtitle: const Text('Create and review school years'),
          onTap: () => Navigator.of(context).push(
            MaterialPageRoute(
              builder: (_) => AcademicListScreen<AcademicYearItem>(
                title: 'Academic years',
                deps: deps,
                loader: deps.academicApi.fetchAcademicYears,
                label: (item) => '${item.name} (${item.code}) — ${item.status}',
                subtitle: (item) => 'ID: ${item.id}',
                onCreate: () async {
                  await Navigator.of(context).push(
                    MaterialPageRoute(builder: (_) => AcademicYearFormScreen(deps: deps)),
                  );
                },
              ),
            ),
          ),
        ),
        ListTile(
          leading: const Icon(Icons.class_),
          title: const Text('Classes & sections'),
          subtitle: const Text('Add classes (optionally with a first section)'),
          onTap: () => Navigator.of(context).push(
            MaterialPageRoute(
              builder: (_) => AcademicListScreen<SchoolClassItem>(
                title: 'Classes',
                deps: deps,
                loader: deps.academicApi.fetchClasses,
                label: (item) => '${item.name} (${item.code}) — ${item.status}',
                subtitle: (item) => 'ID: ${item.id}',
                onCreate: () async {
                  await Navigator.of(context).push(
                    MaterialPageRoute(builder: (_) => SchoolClassFormScreen(deps: deps)),
                  );
                },
              ),
            ),
          ),
        ),
        ListTile(
          leading: const Icon(Icons.grid_view),
          title: const Text('Sections'),
          subtitle: const Text('Add a section under an existing class'),
          onTap: () => Navigator.of(context).push(
            MaterialPageRoute(
              builder: (_) => AcademicListScreen<SectionItem>(
                title: 'Sections',
                deps: deps,
                loader: deps.academicApi.fetchSections,
                label: (item) => '${item.name} — ${item.status}',
                subtitle: (item) => 'Section ID: ${item.id}\nClass ID: ${item.classId}',
                onCreate: () async {
                  await Navigator.of(context).push(
                    MaterialPageRoute(builder: (_) => SectionFormScreen(deps: deps)),
                  );
                },
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
                subtitle: (item) => 'ID: ${item.id}',
                onCreate: () async {
                  await Navigator.of(context).push(
                    MaterialPageRoute(builder: (_) => SubjectFormScreen(deps: deps)),
                  );
                },
              ),
            ),
          ),
        ),
        ListTile(
          leading: const Icon(Icons.person_pin),
          title: const Text('Teacher assignments'),
          subtitle: const Text('Link a teacher to a class section'),
          onTap: () => Navigator.of(context).push(
            MaterialPageRoute(
              builder: (_) => AcademicListScreen<TeacherAssignmentItem>(
                title: 'Teacher assignments',
                deps: deps,
                loader: deps.academicApi.fetchTeacherAssignments,
                label: (item) => '${item.assignmentRole} — ${item.status}',
                subtitle: (item) =>
                    'ID: ${item.id}\nTeacher user: ${item.teacherUserId}\nSection: ${item.sectionId}',
                onCreate: () async {
                  await Navigator.of(context).push(
                    MaterialPageRoute(builder: (_) => TeacherAssignmentFormScreen(deps: deps)),
                  );
                },
              ),
            ),
          ),
        ),
      ],
    );
  }
}
