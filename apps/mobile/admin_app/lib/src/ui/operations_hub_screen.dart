import 'package:flutter/material.dart';

import '../app/admin_dependencies.dart';
import '../operations/admin_operations_api.dart';
import '../operations/operations_models.dart';
import 'admin_widgets.dart';
import 'format.dart';
import 'imports_hub_screen.dart';
import 'people_list_screen.dart';

class OperationsHubScreen extends StatelessWidget {
  const OperationsHubScreen({required this.deps, super.key});

  final AdminDependencies deps;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        Text('Day-to-day operations', style: theme.textTheme.titleLarge),
        const SizedBox(height: 4),
        Text(
          'Buses, cards, readers, and the events they generate.',
          style: theme.textTheme.bodyMedium?.copyWith(
            color: theme.colorScheme.onSurfaceVariant,
          ),
        ),
        const SizedBox(height: 16),
        AdminSectionCard(
          icon: Icons.dashboard_outlined,
          title: 'Operations overview',
          subtitle: 'Live counts for buses, trips, and events',
          onTap: () => Navigator.of(context).push(
            MaterialPageRoute(
              builder: (_) => _OperationsOverviewScreen(deps: deps),
            ),
          ),
        ),
        const SizedBox(height: 12),
        AdminSectionCard(
          icon: Icons.upload_outlined,
          title: 'CSV imports',
          subtitle: 'Validate and apply school onboarding data',
          onTap: () => Navigator.of(context).push(
            MaterialPageRoute(builder: (_) => ImportsHubScreen(deps: deps)),
          ),
        ),
        const SizedBox(height: 12),
        AdminSectionCard(
          icon: Icons.credit_card_outlined,
          title: 'Card inventory',
          subtitle: 'Physical ID cards and their status',
          onTap: () => Navigator.of(context).push(
            MaterialPageRoute(
              builder: (_) => PeopleListScreen<CardItem>(
                title: 'Cards',
                deps: deps,
                loader: ({search, filter}) => deps.operationsApi.fetchCards(search: search),
                label: (c) => 'Card ${c.hfUid ?? c.id.substring(0, 8)}',
                subtitle: (c) => 'Status: ${prettifyLabel(c.status)}',
              ),
            ),
          ),
        ),
        const SizedBox(height: 12),
        AdminSectionCard(
          icon: Icons.sensors_outlined,
          title: 'RFID readers',
          subtitle: 'Gate readers and their status',
          onTap: () => _openList<RfidReaderItem>(
            context,
            title: 'RFID readers',
            loader: () => deps.operationsApi.fetchReaders(),
            label: (r) => r.name,
            subtitle: (r) => prettifyLabel(r.status),
          ),
        ),
        const SizedBox(height: 12),
        AdminSectionCard(
          icon: Icons.list_alt_outlined,
          title: 'Recent RFID events',
          subtitle: 'View only — events cannot be edited',
          onTap: () => _openList<RfidEventItem>(
            context,
            title: 'RFID events',
            loader: () => deps.operationsApi.fetchRfidEvents(),
            label: (e) => 'Tap · ${e.hfUid ?? 'Unknown card'}',
            subtitle: (e) =>
                '${formatDateTimeString(e.occurredAt)} · ${e.processingStatus == null ? 'Unprocessed' : prettifyLabel(e.processingStatus!)}',
          ),
        ),
        const SizedBox(height: 12),
        AdminSectionCard(
          icon: Icons.directions_bus_outlined,
          title: 'Buses',
          subtitle: 'Vehicles in your fleet',
          onTap: () => _openList<BusItem>(
            context,
            title: 'Buses',
            loader: () => deps.operationsApi.fetchBuses(),
            label: (b) => b.displayName,
            subtitle: (b) => prettifyLabel(b.status),
          ),
        ),
        const SizedBox(height: 12),
        AdminSectionCard(
          icon: Icons.route_outlined,
          title: 'Trips',
          subtitle: 'Scheduled bus trips by service date',
          onTap: () => _openList<TripItem>(
            context,
            title: 'Trips',
            loader: () => deps.operationsApi.fetchTrips(),
            label: (t) => formatDateString(t.serviceDate),
            subtitle: (t) => 'Trip · ${prettifyLabel(t.status)}',
          ),
        ),
        const SizedBox(height: 12),
        AdminSectionCard(
          icon: Icons.airport_shuttle_outlined,
          title: 'Student transport',
          subtitle: 'Which students ride which trips',
          onTap: () => _openList<TransportAssignmentItem>(
            context,
            title: 'Transport assignments',
            loader: () => deps.operationsApi.fetchTransportAssignments(),
            label: (a) => 'Transport assignment',
            subtitle: (a) => prettifyLabel(a.status),
          ),
        ),
        const SizedBox(height: 12),
        AdminSectionCard(
          icon: Icons.people_outline,
          title: 'Bus attendants',
          subtitle: 'Staff assigned to bus duty',
          onTap: () => _openList<TransportAttendantItem>(
            context,
            title: 'Attendants',
            loader: () => deps.operationsApi.fetchTransportAttendants(),
            label: (a) => a.employeeCode,
            subtitle: (a) => prettifyLabel(a.status),
          ),
        ),
        const SizedBox(height: 12),
        AdminSectionCard(
          icon: Icons.alt_route_outlined,
          title: 'Routes',
          subtitle: 'Bus routes and stops',
          onTap: () => _openList<RouteItem>(
            context,
            title: 'Routes',
            loader: () => deps.operationsApi.fetchRoutes(),
            label: (r) => r.name,
            subtitle: (r) => prettifyLabel(r.status),
          ),
        ),
        const SizedBox(height: 12),
        AdminSectionCard(
          icon: Icons.nfc_outlined,
          title: 'Boarding records',
          subtitle: 'Read-only NFC boarding history',
          onTap: () => _openList<BoardingRecordItem>(
            context,
            title: 'Boarding',
            loader: () => deps.operationsApi.fetchBoardingRecords(),
            label: (b) => prettifyLabel(b.eventType),
            subtitle: (b) => formatDateTimeString(b.occurredAt),
          ),
        ),
        const SizedBox(height: 12),
        AdminSectionCard(
          icon: Icons.gps_fixed_outlined,
          title: 'GPS samples',
          subtitle: 'Historical trip locations',
          onTap: () => _openList<LocationSampleItem>(
            context,
            title: 'GPS history',
            loader: () => deps.operationsApi.fetchLocationSamples(),
            label: (s) => '${s.latitude}, ${s.longitude}',
            subtitle: (s) => formatDateTimeString(s.occurredAt),
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
    String Function(T)? subtitle,
  }) {
    Navigator.of(context).push(
      MaterialPageRoute(
        builder: (_) => PeopleListScreen<T>(
          title: title,
          deps: deps,
          loader: ({search, filter}) => loader(),
          label: label,
          subtitle: subtitle,
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
    setState(() => _error = null);
    try {
      final data = await widget.deps.operationsApi.fetchOperationsOverview();
      if (mounted) setState(() => _overview = data);
    } on AdminOperationsUnauthorized {
      if (mounted) setState(() => _error = 'Session expired. Sign in again.');
    } on AdminOperationsApiFailure catch (e) {
      if (mounted) setState(() => _error = e.message);
    } catch (_) {
      if (mounted) setState(() => _error = 'Could not load the operations overview.');
    }
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Scaffold(
      appBar: AppBar(title: const Text('Operations overview')),
      body: _error != null
          ? ErrorRetry(message: _error!, onRetry: _load)
          : _overview == null
              ? const Center(child: CircularProgressIndicator())
              : RefreshIndicator(
                  onRefresh: _load,
                  child: GridView.count(
                    padding: const EdgeInsets.all(16),
                    crossAxisCount: 2,
                    mainAxisSpacing: 12,
                    crossAxisSpacing: 12,
                    childAspectRatio: 1.35,
                    children: [
                      _metricCard(theme, Icons.directions_bus_outlined, 'Active buses', _overview!.activeBuses),
                      _metricCard(theme, Icons.route_outlined, 'Active trips', _overview!.activeTrips),
                      _metricCard(
                        theme,
                        Icons.airport_shuttle_outlined,
                        'Transport assignments',
                        _overview!.activeTransportAssignments,
                      ),
                      _metricCard(
                        theme,
                        Icons.sensors_outlined,
                        'RFID events (24h)',
                        _overview!.rfidEventsLast24h,
                      ),
                      _metricCard(
                        theme,
                        Icons.nfc_outlined,
                        'Boarding events (24h)',
                        _overview!.boardingEventsLast24h,
                      ),
                    ],
                  ),
                ),
    );
  }

  Widget _metricCard(ThemeData theme, IconData icon, String label, int value) {
    final scheme = theme.colorScheme;
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(icon, color: scheme.primary),
            const SizedBox(height: 8),
            Text(
              '$value',
              style: theme.textTheme.headlineMedium?.copyWith(fontWeight: FontWeight.w800),
            ),
            const SizedBox(height: 2),
            Text(
              label,
              style: theme.textTheme.bodyMedium?.copyWith(
                color: scheme.onSurfaceVariant,
              ),
            ),
          ],
        ),
      ),
    );
  }
}
