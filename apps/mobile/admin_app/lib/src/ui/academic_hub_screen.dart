import 'package:flutter/material.dart';

import '../academic/academic_models.dart';
import '../app/admin_dependencies.dart';
import 'academic_form_screens.dart';
import 'academic_list_screen.dart';
import 'admin_widgets.dart';
import 'format.dart';

class AcademicHubScreen extends StatelessWidget {
  const AcademicHubScreen({required this.deps, super.key});

  final AdminDependencies deps;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        Text('Set up the school year', style: theme.textTheme.titleLarge),
        const SizedBox(height: 4),
        Text(
          'Years, classes, subjects, and who teaches them.',
          style: theme.textTheme.bodyMedium?.copyWith(
            color: theme.colorScheme.onSurfaceVariant,
          ),
        ),
        const SizedBox(height: 16),
        AdminSectionCard(
          icon: Icons.calendar_month_outlined,
          title: 'Academic years',
          subtitle: 'Create and review school years',
          onTap: () => Navigator.of(context).push(
            MaterialPageRoute(
              builder: (_) => AcademicListScreen<AcademicYearItem>(
                title: 'Academic years',
                deps: deps,
                loader: deps.academicApi.fetchAcademicYears,
                label: (item) => item.name,
                subtitle: (item) => '${item.code} · ${prettifyLabel(item.status)}',
                onCreate: () async {
                  await Navigator.of(context).push(
                    MaterialPageRoute(builder: (_) => AcademicYearFormScreen(deps: deps)),
                  );
                },
              ),
            ),
          ),
        ),
        const SizedBox(height: 12),
        AdminSectionCard(
          icon: Icons.class_outlined,
          title: 'Classes & sections',
          subtitle: 'Add classes (optionally with a first section)',
          onTap: () => Navigator.of(context).push(
            MaterialPageRoute(
              builder: (_) => AcademicListScreen<SchoolClassItem>(
                title: 'Classes',
                deps: deps,
                loader: deps.academicApi.fetchClasses,
                label: (item) => item.name,
                subtitle: (item) => '${item.code} · ${prettifyLabel(item.status)}',
                onCreate: () async {
                  await Navigator.of(context).push(
                    MaterialPageRoute(builder: (_) => SchoolClassFormScreen(deps: deps)),
                  );
                },
              ),
            ),
          ),
        ),
        const SizedBox(height: 12),
        AdminSectionCard(
          icon: Icons.grid_view_outlined,
          title: 'Sections',
          subtitle: 'Add a section under an existing class',
          onTap: () => Navigator.of(context).push(
            MaterialPageRoute(
              builder: (_) => AcademicListScreen<SectionItem>(
                title: 'Sections',
                deps: deps,
                loader: deps.academicApi.fetchSections,
                label: (item) => item.name,
                subtitle: (item) => prettifyLabel(item.status),
                onCreate: () async {
                  await Navigator.of(context).push(
                    MaterialPageRoute(builder: (_) => SectionFormScreen(deps: deps)),
                  );
                },
              ),
            ),
          ),
        ),
        const SizedBox(height: 12),
        AdminSectionCard(
          icon: Icons.menu_book_outlined,
          title: 'Subjects',
          subtitle: 'The subjects taught at your school',
          onTap: () => Navigator.of(context).push(
            MaterialPageRoute(
              builder: (_) => AcademicListScreen<SubjectItem>(
                title: 'Subjects',
                deps: deps,
                loader: deps.academicApi.fetchSubjects,
                label: (item) => item.name,
                subtitle: (item) => '${item.code} · ${prettifyLabel(item.status)}',
                onCreate: () async {
                  await Navigator.of(context).push(
                    MaterialPageRoute(builder: (_) => SubjectFormScreen(deps: deps)),
                  );
                },
              ),
            ),
          ),
        ),
        const SizedBox(height: 12),
        AdminSectionCard(
          icon: Icons.person_pin_outlined,
          title: 'Teacher assignments',
          subtitle: 'Link a teacher to a class section',
          onTap: () => Navigator.of(context).push(
            MaterialPageRoute(
              builder: (_) => AcademicListScreen<TeacherAssignmentItem>(
                title: 'Teacher assignments',
                deps: deps,
                loader: deps.academicApi.fetchTeacherAssignments,
                label: (item) => prettifyLabel(item.assignmentRole),
                subtitle: (item) => prettifyLabel(item.status),
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
