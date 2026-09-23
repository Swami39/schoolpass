import 'package:flutter/material.dart';

import '../app/admin_dependencies.dart';
import '../people/people_models.dart';
import 'admin_widgets.dart';
import 'format.dart';
import 'guardian_detail_screen.dart';
import 'guardian_form_screen.dart';
import 'people_list_screen.dart';
import 'staff_detail_screen.dart';
import 'staff_form_screen.dart';
import 'student_detail_screen.dart';
import 'student_form_screen.dart';

class PeopleHubScreen extends StatelessWidget {
  const PeopleHubScreen({required this.deps, super.key});

  final AdminDependencies deps;

  static Widget staffList(BuildContext context, AdminDependencies deps, {bool useScaffold = true}) {
    return PeopleListScreen<StaffListItem>(
      title: 'Staff',
      deps: deps,
      useScaffold: useScaffold,
      loader: ({search, filter}) => deps.peopleApi.fetchStaff(search: search, staffType: filter),
      filterOptions: const ['teacher', 'office', 'finance', 'attendant', 'bus_attendant'],
      label: (item) => prettifyLabel(item.staffType),
      subtitle: (item) => item.email ?? item.employeeCode ?? 'No contact info',
      onTap: (item) => Navigator.of(context).push(
        MaterialPageRoute(builder: (_) => StaffDetailScreen(deps: deps, staffId: item.id)),
      ),
      onCreate: () => Navigator.of(context).push(
        MaterialPageRoute(builder: (_) => StaffFormScreen(deps: deps)),
      ),
    );
  }

  static Widget studentsList(BuildContext context, AdminDependencies deps, {bool useScaffold = true}) {
    return PeopleListScreen<StudentDetail>(
      title: 'Students',
      deps: deps,
      useScaffold: useScaffold,
      loader: ({search, filter}) => deps.peopleApi.fetchStudents(search: search, status: filter),
      filterOptions: const ['active', 'withdrawn'],
      label: (item) => item.displayName,
      subtitle: (item) => 'Admission ${item.admissionNo} · ${prettifyLabel(item.status)}',
      onTap: (item) => Navigator.of(context).push(
        MaterialPageRoute(builder: (_) => StudentDetailScreen(deps: deps, studentId: item.id)),
      ),
      onCreate: () async {
        await Navigator.of(context).push(
          MaterialPageRoute(builder: (_) => StudentFormScreen(deps: deps)),
        );
      },
    );
  }

  static Widget guardiansList(BuildContext context, AdminDependencies deps, {bool useScaffold = true}) {
    return PeopleListScreen<GuardianDetail>(
      title: 'Guardians',
      deps: deps,
      useScaffold: useScaffold,
      loader: ({search, filter}) => deps.peopleApi.fetchGuardians(),
      label: (item) => item.displayName,
      subtitle: (item) => [
        prettifyLabel(item.status),
        if (item.email != null) item.email!,
        if (item.userId != null) 'Parent app login linked',
      ].join(' · '),
      onTap: (item) => Navigator.of(context).push(
        MaterialPageRoute(builder: (_) => GuardianDetailScreen(deps: deps, guardianId: item.id)),
      ),
      onCreate: () async {
        await Navigator.of(context).push(
          MaterialPageRoute(builder: (_) => GuardianFormScreen(deps: deps)),
        );
      },
    );
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        Text('Who is in your school?', style: theme.textTheme.titleLarge),
        const SizedBox(height: 4),
        Text(
          'Manage everyone connected to your students.',
          style: theme.textTheme.bodyMedium?.copyWith(
            color: theme.colorScheme.onSurfaceVariant,
          ),
        ),
        const SizedBox(height: 16),
        AdminSectionCard(
          icon: Icons.badge_outlined,
          title: 'Staff',
          subtitle: 'Teachers, attendants, and office staff',
          onTap: () => Navigator.of(context).push(
            MaterialPageRoute(builder: (_) => staffList(context, deps)),
          ),
        ),
        const SizedBox(height: 12),
        AdminSectionCard(
          icon: Icons.school_outlined,
          title: 'Students',
          subtitle: 'Admissions, enrollments, and cards',
          onTap: () => Navigator.of(context).push(
            MaterialPageRoute(builder: (_) => studentsList(context, deps)),
          ),
        ),
        const SizedBox(height: 12),
        AdminSectionCard(
          icon: Icons.family_restroom_outlined,
          title: 'Guardians',
          subtitle: 'Parents with Parent app logins',
          onTap: () => Navigator.of(context).push(
            MaterialPageRoute(builder: (_) => guardiansList(context, deps)),
          ),
        ),
      ],
    );
  }
}
