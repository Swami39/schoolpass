import 'package:flutter/material.dart';

import '../app/admin_dependencies.dart';
import '../people/people_models.dart';
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

  @override
  Widget build(BuildContext context) {
    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        ListTile(
          leading: const Icon(Icons.badge),
          title: const Text('Staff'),
          onTap: () => Navigator.of(context).push(
            MaterialPageRoute(
              builder: (_) => PeopleListScreen<StaffListItem>(
                title: 'Staff',
                deps: deps,
                loader: ({search, filter}) => deps.peopleApi.fetchStaff(search: search, staffType: filter),
                filterOptions: const ['teacher', 'office', 'finance', 'attendant', 'bus_attendant'],
                label: (item) => '${item.staffType} — ${item.email ?? item.employeeCode ?? item.id}',
                onTap: (item) => Navigator.of(context).push(
                  MaterialPageRoute(builder: (_) => StaffDetailScreen(deps: deps, staffId: item.id)),
                ),
                onCreate: () => Navigator.of(context).push(
                  MaterialPageRoute(builder: (_) => StaffFormScreen(deps: deps)),
                ),
              ),
            ),
          ),
        ),
        ListTile(
          leading: const Icon(Icons.school),
          title: const Text('Students'),
          onTap: () => Navigator.of(context).push(
            MaterialPageRoute(
              builder: (_) => PeopleListScreen<StudentDetail>(
                title: 'Students',
                deps: deps,
                loader: ({search, filter}) => deps.peopleApi.fetchStudents(search: search, status: filter),
                filterOptions: const ['active', 'withdrawn'],
                label: (item) => '${item.displayName} (${item.admissionNo}) — ${item.status}',
                onTap: (item) => Navigator.of(context).push(
                  MaterialPageRoute(builder: (_) => StudentDetailScreen(deps: deps, studentId: item.id)),
                ),
                onCreate: () async {
                  await Navigator.of(context).push(
                    MaterialPageRoute(builder: (_) => StudentFormScreen(deps: deps)),
                  );
                },
              ),
            ),
          ),
        ),
        ListTile(
          leading: const Icon(Icons.family_restroom),
          title: const Text('Guardians'),
          onTap: () => Navigator.of(context).push(
            MaterialPageRoute(
              builder: (_) => PeopleListScreen<GuardianDetail>(
                title: 'Guardians',
                deps: deps,
                loader: ({search, filter}) => deps.peopleApi.fetchGuardians(),
                label: (item) => '${item.displayName} — ${item.status}',
                onTap: (item) => Navigator.of(context).push(
                  MaterialPageRoute(builder: (_) => GuardianDetailScreen(deps: deps, guardianId: item.id)),
                ),
                onCreate: () async {
                  await Navigator.of(context).push(
                    MaterialPageRoute(builder: (_) => GuardianFormScreen(deps: deps)),
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
