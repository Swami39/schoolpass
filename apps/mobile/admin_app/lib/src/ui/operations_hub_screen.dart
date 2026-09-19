import 'package:flutter/material.dart';

import '../app/admin_dependencies.dart';
import '../operations/operations_models.dart';
import 'imports_hub_screen.dart';
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
          leading: const Icon(Icons.dashboard),
          title: const Text('Operations overview'),
          onTap: () => Navigator.of(context).push(
            MaterialPageRoute(
              builder: (_) => _OperationsOverviewScreen(deps: deps),
            ),
          ),
        ),
        ListTile(
          leading: const Icon(Icons.upload),
          title: const Text('CSV imports'),
          subtitle: const Text('Validate and apply school onboarding data'),
          onTap: () => Navigator.of(context).push(
            MaterialPageRoute(builder: (_) => ImportsHubScreen(deps: deps)),
          ),
        ),
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
        ListTile(
          leading: const Icon(Icons.people),
          title: const Text('Bus attendants'),
          onTap: () => _openList<TransportAttendantItem>(
            context,
            title: 'Attendants',
            loader: () => deps.operationsApi.fetchTransportAttendants(),
            label: (a) => '${a.employeeCode} — ${a.status}',
          ),
        ),
        ListTile(
          leading: const Icon(Icons.alt_route),
          title: const Text('Routes'),
          onTap: () => _openList<RouteItem>(
            context,
            title: 'Routes',
            loader: () => deps.operationsApi.fetchRoutes(),
            label: (r) => '${r.name} — ${r.status}',
          ),
        ),
        ListTile(
          leading: const Icon(Icons.nfc),
          title: const Text('Boarding records'),
          subtitle: const Text('Read-only NFC boarding history'),
          onTap: () => _openList<BoardingRecordItem>(
            context,
            title: 'Boarding',
            loader: () => deps.operationsApi.fetchBoardingRecords(),
            label: (b) => '${b.eventType} — ${b.occurredAt}',
          ),
        ),
        ListTile(
          leading: const Icon(Icons.gps_fixed),
          title: const Text('GPS samples'),
          subtitle: const Text('Historical trip locations'),
          onTap: () => _openList<LocationSampleItem>(
            context,
            title: 'GPS history',
            loader: () => deps.operationsApi.fetchLocationSamples(),
            label: (s) => '${s.latitude}, ${s.longitude} @ ${s.occurredAt}',
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

class _OperationsOverviewScreen extends StatefulWidget {
  const _OperationsOverviewScreen({required this.deps});

  final AdminDependencies deps;

  @override
  State<_OperationsOverviewScreen> createState() => _OperationsOverviewScreenState();
}

class _OperationsOverviewScreenState extends State<_OperationsOverviewScreen> {
  OperationsOverview? _overview;
  String? _error;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    try {
      final data = await widget.deps.operationsApi.fetchOperationsOverview();
      setState(() => _overview = data);
    } catch (e) {
      setState(() => _error = e.toString());
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Operations overview')),
      body: _error != null
          ? Center(child: Text(_error!))
          : _overview == null
              ? const Center(child: CircularProgressIndicator())
              : ListView(
                  padding: const EdgeInsets.all(16),
                  children: [
                    _metric('Active buses', _overview!.activeBuses),
                    _metric('Active trips', _overview!.activeTrips),
                    _metric('Transport assignments', _overview!.activeTransportAssignments),
                    _metric('RFID events (24h)', _overview!.rfidEventsLast24h),
                    _metric('Boarding events (24h)', _overview!.boardingEventsLast24h),
                  ],
                ),
    );
  }

  Widget _metric(String label, int value) => ListTile(
        title: Text(label),
        trailing: Text('$value', style: Theme.of(context).textTheme.titleLarge),
      );
}
