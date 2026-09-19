import 'package:flutter/material.dart';

import '../app/admin_dependencies.dart';
import '../operations/operations_models.dart';
import 'people_list_screen.dart';

class OperationsHubScreen extends StatelessWidget {
  const OperationsHubScreen({required this.deps, super.key});

  final AdminDependencies deps;

  @override
  Widget build(BuildContext context) {
    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        ListTile(
          leading: const Icon(Icons.credit_card),
          title: const Text('Card inventory'),
          onTap: () => Navigator.of(context).push(
            MaterialPageRoute(
              builder: (_) => PeopleListScreen<CardItem>(
                title: 'Cards',
                deps: deps,
                loader: ({search, filter}) => deps.operationsApi.fetchCards(search: search),
                label: (c) => '${c.hfUid ?? c.id.substring(0, 8)} — ${c.status}',
              ),
            ),
          ),
        ),
        ListTile(
          leading: const Icon(Icons.sensors),
          title: const Text('RFID readers'),
          onTap: () => _openList<RfidReaderItem>(
            context,
            title: 'RFID readers',
            loader: () => deps.operationsApi.fetchReaders(),
            label: (r) => '${r.name} — ${r.status}',
          ),
        ),
        ListTile(
          leading: const Icon(Icons.list_alt),
          title: const Text('Recent RFID events'),
          subtitle: const Text('View only — events cannot be edited'),
          onTap: () => _openList<RfidEventItem>(
            context,
            title: 'RFID events',
            loader: () => deps.operationsApi.fetchRfidEvents(),
            label: (e) => '${e.occurredAt} — ${e.hfUid ?? 'unknown'} (${e.processingStatus ?? '—'})',
          ),
        ),
        ListTile(
          leading: const Icon(Icons.directions_bus),
          title: const Text('Buses'),
          onTap: () => _openList<BusItem>(
            context,
            title: 'Buses',
            loader: () => deps.operationsApi.fetchBuses(),
            label: (b) => '${b.displayName} — ${b.status}',
          ),
        ),
        ListTile(
          leading: const Icon(Icons.route),
          title: const Text('Trips'),
          onTap: () => _openList<TripItem>(
            context,
            title: 'Trips',
            loader: () => deps.operationsApi.fetchTrips(),
            label: (t) => '${t.serviceDate} — ${t.status}',
          ),
        ),
        ListTile(
          leading: const Icon(Icons.airport_shuttle),
          title: const Text('Student transport'),
          onTap: () => _openList<TransportAssignmentItem>(
            context,
            title: 'Transport assignments',
            loader: () => deps.operationsApi.fetchTransportAssignments(),
            label: (a) => 'Student ${a.studentId.substring(0, 8)}… — ${a.status}',
          ),
        ),
      ],
    );
  }

  void _openList<T>(
    BuildContext context, {
    required String title,
    required Future<List<T>> Function() loader,
    required String Function(T) label,
  }) {
    Navigator.of(context).push(
      MaterialPageRoute(
        builder: (_) => PeopleListScreen<T>(
          title: title,
          deps: deps,
          loader: ({search, filter}) => loader(),
          label: label,
        ),
      ),
    );
  }
}
